from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.wallets.models import Wallet
from apps.wallets.services.wallet_service import create_wallet, get_user_wallets, get_wallet_balance
from apps.common.exceptions import LedgerError

User = get_user_model()

class WalletServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password", email="test1@example.com")

    def test_create_wallet_success(self):
        wallet = create_wallet(user=self.user, name="Main Savings", currency="USD")
        self.assertEqual(wallet.name, "Main Savings")
        self.assertEqual(wallet.currency, "USD")
        self.assertEqual(wallet.status, Wallet.Status.ACTIVE)
        self.assertEqual(wallet.user, self.user)
        self.assertIsNotNone(wallet.id)

    def test_create_wallet_normalises_currency(self):
        wallet = create_wallet(user=self.user, name="Euro Wallet", currency=" eur ")
        self.assertEqual(wallet.currency, "EUR")

    def test_create_wallet_duplicate_name_currency_fails(self):
        create_wallet(user=self.user, name="Savings", currency="USD")
        with self.assertRaisesMessage(ValueError, "already exists"):
            create_wallet(user=self.user, name="Savings", currency="USD")

    def test_create_wallet_different_currency_same_name_succeeds(self):
        create_wallet(user=self.user, name="Savings", currency="USD")
        wallet = create_wallet(user=self.user, name="Savings", currency="EUR")
        self.assertEqual(wallet.currency, "EUR")

    def test_create_wallet_invalid_currency_fails(self):
        # Too long
        with self.assertRaisesMessage(ValueError, "Invalid currency code"):
            create_wallet(user=self.user, name="Savings", currency="USDC")
        # Too short
        with self.assertRaisesMessage(ValueError, "Invalid currency code"):
            create_wallet(user=self.user, name="Savings", currency="US")
        # Numbers involved
        with self.assertRaisesMessage(ValueError, "Invalid currency code"):
            create_wallet(user=self.user, name="Savings", currency="US1")

    def test_get_user_wallets_returns_only_active(self):
        w1 = create_wallet(user=self.user, name="Active 1", currency="USD")
        w2 = create_wallet(user=self.user, name="Active 2", currency="EUR")
        
        # Manually archive one
        w3 = create_wallet(user=self.user, name="Archived", currency="GBP")
        w3.status = Wallet.Status.ARCHIVED
        w3.save()

        wallets = list(get_user_wallets(self.user))
        self.assertEqual(len(wallets), 2)
        self.assertIn(w1, wallets)
        self.assertIn(w2, wallets)
        self.assertNotIn(w3, wallets)

    def test_get_wallet_balance_not_found_raises(self):
        other_user = User.objects.create_user(username="other", password="password", email="test2@example.com")
        wallet = create_wallet(user=other_user, name="Other Wallet", currency="USD")
        
        with self.assertRaisesMessage(LedgerError, "Wallet not found or access denied"):
            get_wallet_balance(user=self.user, wallet_id=wallet.id)
