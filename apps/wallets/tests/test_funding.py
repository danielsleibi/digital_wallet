from decimal import Decimal
from django.db.models import Sum
from django.test import TransactionTestCase
from django.contrib.auth import get_user_model
from apps.wallets.models import Wallet
from apps.ledger.models import LedgerPosting, Transaction
from apps.common.auth.jwt import create_access_token
from django.test import Client

User = get_user_model()

class WalletFundingTests(TransactionTestCase):
    """
    Tests for the POST /wallets/{wallet_id}/fund endpoint.
    Uses TransactionTestCase to properly test transactional behavior.
    """
    def setUp(self):
        # Create SYSTEM user and system wallets
        self.system_user, _ = User.objects.get_or_create(
            username="SYSTEM",
            defaults={
                "email": "system@digitalwallet.local",
                "is_active": False,
                "is_system": True
            }
        )
        # Create system wallets for USD (use get_or_create since DB persists between TransactionTestCase tests)
        self.equity_wallet, _ = Wallet.objects.get_or_create(
            user=self.system_user,
            name="EQUITY",
            currency="USD",
            defaults={"status": Wallet.Status.ACTIVE}
        )
        self.income_wallet, _ = Wallet.objects.get_or_create(
            user=self.system_user,
            name="INCOME",
            currency="USD",
            defaults={"status": Wallet.Status.ACTIVE}
        )
        # Create a system wallet in EUR
        self.equity_eur, _ = Wallet.objects.get_or_create(
            user=self.system_user,
            name="EQUITY",
            currency="EUR",
            defaults={"status": Wallet.Status.ACTIVE}
        )

        # Create regular user and wallet
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123",
            email="test@example.com"
        )
        self.user_wallet = Wallet.objects.create(
            user=self.user,
            name="My Wallet",
            currency="USD",
            status=Wallet.Status.ACTIVE
        )
        self.user_wallet_eur = Wallet.objects.create(
            user=self.user,
            name="EUR Wallet",
            currency="EUR",
            status=Wallet.Status.ACTIVE
        )

        # Create JWT token and client
        self.token = create_access_token(str(self.user.id))
        self.client = Client(
            HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )

    def _get_balance(self, wallet):
        return LedgerPosting.objects.filter(wallet=wallet).aggregate(total=Sum("amount"))["total"] or Decimal("0")

    def test_fund_wallet_success(self):
        """Test successful funding of wallet from EQUITY system wallet."""
        response = self.client.post(
            f"/api/wallets/{self.user_wallet.id}/fund",
            data={
                "amount": "150.00",
                "description": "Initial funding",
                "system_wallet_name": "EQUITY"
            },
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["message"], "Wallet funded successfully")
        self.assertEqual(data["amount"], "150.00")
        self.assertEqual(data["wallet_id"], str(self.user_wallet.id))

        # Verify balances
        self.assertEqual(self._get_balance(self.user_wallet), Decimal("150.00"))
        self.assertEqual(self._get_balance(self.equity_wallet), Decimal("-150.00"))

        # Verify ledger invariant
        total = LedgerPosting.objects.aggregate(total=Sum("amount"))["total"] or Decimal("0")
        self.assertEqual(total, Decimal("0"))

    def test_fund_wallet_with_income_wallet(self):
        """Test funding using INCOME system wallet."""
        response = self.client.post(
            f"/api/wallets/{self.user_wallet.id}/fund",
            data={
                "amount": "200.00",
                "description": "Income funding",
                "system_wallet_name": "INCOME"
            },
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._get_balance(self.user_wallet), Decimal("200.00"))
        self.assertEqual(self._get_balance(self.income_wallet), Decimal("-200.00"))

    def test_fund_wallet_not_own_wallet(self):
        """Test that user cannot fund another user's wallet."""
        other_user = User.objects.create_user(username="other", password="pass", email="other@example.com")
        other_wallet = Wallet.objects.create(
            user=other_user,
            name="Other Wallet",
            currency="USD",
            status=Wallet.Status.ACTIVE
        )
        response = self.client.post(
            f"/api/wallets/{other_wallet.id}/fund",
            data={
                "amount": "100.00",
                "system_wallet_name": "EQUITY"
            },
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found or access denied", response.json()["detail"])

    def test_fund_wallet_inactive_target(self):
        """Test that funding an inactive wallet fails."""
        self.user_wallet.status = Wallet.Status.ARCHIVED
        self.user_wallet.save()
        response = self.client.post(
            f"/api/wallets/{self.user_wallet.id}/fund",
            data={
                "amount": "100.00",
                "system_wallet_name": "EQUITY"
            },
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 404)

    def test_fund_wallet_system_wallet_target(self):
        """Test that cannot fund a system wallet (since user doesn't own it)."""
        response = self.client.post(
            f"/api/wallets/{self.equity_wallet.id}/fund",
            data={
                "amount": "100.00",
                "system_wallet_name": "EQUITY"
            },
            content_type="application/json"
        )
        # System wallet belongs to SYSTEM user, not the authenticated user -> 404
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found or access denied", response.json()["detail"])

    def test_fund_wallet_missing_system_wallet(self):
        """Test that funding fails when specified system wallet doesn't exist."""
        response = self.client.post(
            f"/api/wallets/{self.user_wallet.id}/fund",
            data={
                "amount": "100.00",
                "system_wallet_name": "NONEXISTENT"
            },
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("not found or inactive", response.json()["detail"])

    def test_fund_wallet_system_wallet_inactive(self):
        """Test that funding fails when specified system wallet is inactive."""
        self.equity_wallet.status = Wallet.Status.ARCHIVED
        self.equity_wallet.save()
        response = self.client.post(
            f"/api/wallets/{self.user_wallet.id}/fund",
            data={
                "amount": "100.00",
                "system_wallet_name": "EQUITY"
            },
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("not found or inactive", response.json()["detail"])

    def test_fund_wallet_invalid_amount_zero(self):
        """Test that zero amount is rejected."""
        response = self.client.post(
            f"/api/wallets/{self.user_wallet.id}/fund",
            data={
                "amount": "0",
                "system_wallet_name": "EQUITY"
            },
            content_type="application/json"
        )
        # Pydantic validation error returns 422
        self.assertEqual(response.status_code, 422)
        errors = response.json().get('detail', [])
        self.assertIsInstance(errors, list)
        self.assertTrue(any(e.get('type') == 'greater_than' and e.get('msg') == 'Input should be greater than 0' for e in errors))

    def test_fund_wallet_invalid_amount_negative(self):
        """Test that negative amount is rejected."""
        response = self.client.post(
            f"/api/wallets/{self.user_wallet.id}/fund",
            data={
                "amount": "-50.00",
                "system_wallet_name": "EQUITY"
            },
            content_type="application/json"
        )
        # Pydantic validation error returns 422
        self.assertEqual(response.status_code, 422)
        errors = response.json().get('detail', [])
        self.assertIsInstance(errors, list)
        self.assertTrue(any(e.get('type') == 'greater_than' and e.get('msg') == 'Input should be greater than 0' for e in errors))

    def test_fund_wallet_currency_mismatch(self):
        """
        Test that funding a EUR wallet with USD system wallet fails.
        Because there's no EUR system wallet with name "EQUITY" for this user? Actually we have both.
        We'll test that specifying "EQUITY" will find the EUR one if we have it.
        Actually we do have EUR EQUITY, so this test should check that if we specify a system wallet name
        that exists in a different currency, it fails.
        """
        # Use "INCOME" for EUR wallet - we only have USD INCOME, so it should fail
        response = self.client.post(
            f"/api/wallets/{self.user_wallet_eur.id}/fund",
            data={
                "amount": "100.00",
                "system_wallet_name": "INCOME"  # Only have USD INCOME, not EUR
            },
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("not found or inactive", response.json()["detail"])

    def test_fund_wallet_success_with_matching_currency_system_wallet(self):
        """Test that funding a EUR wallet with EUR system wallet succeeds."""
        response = self.client.post(
            f"/api/wallets/{self.user_wallet_eur.id}/fund",
            data={
                "amount": "150.00",
                "system_wallet_name": "EQUITY"  # We have EUR EQUITY
            },
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._get_balance(self.user_wallet_eur), Decimal("150.00"))
        self.assertEqual(self._get_balance(self.equity_eur), Decimal("-150.00"))

    def test_fund_multiple_times_increases_balance(self):
        """Test multiple funding operations accumulate correctly."""
        # First funding
        self.client.post(
            f"/api/wallets/{self.user_wallet.id}/fund",
            data={"amount": "100.00", "system_wallet_name": "EQUITY"},
            content_type="application/json"
        )
        # Second funding
        self.client.post(
            f"/api/wallets/{self.user_wallet.id}/fund",
            data={"amount": "50.00", "system_wallet_name": "INCOME"},
            content_type="application/json"
        )
        self.assertEqual(self._get_balance(self.user_wallet), Decimal("150.00"))
        self.assertEqual(self._get_balance(self.equity_wallet), Decimal("-100.00"))
        self.assertEqual(self._get_balance(self.income_wallet), Decimal("-50.00"))

    def test_large_amount_funding(self):
        """Test funding with a very large amount to ensure precision."""
        response = self.client.post(
            f"/api/wallets/{self.user_wallet.id}/fund",
            data={
                "amount": "999999.999999",
                "system_wallet_name": "EQUITY"
            },
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._get_balance(self.user_wallet), Decimal("999999.999999"))
        self.assertEqual(self._get_balance(self.equity_wallet), Decimal("-999999.999999"))
