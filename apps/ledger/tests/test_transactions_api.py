# apps/ledger/tests/test_transactions_api.py

"""
API integration tests for transaction list and detail endpoints.
Uses Django test client to simulate HTTP requests.
"""

from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.wallets.models import Wallet
from apps.ledger.models import Transaction, LedgerPosting
from apps.common.auth.jwt import create_access_token

User = get_user_model()


class TransactionAPITests(TestCase):
    """Tests for GET /api/transactions/ and GET /api/transactions/{id}/ endpoints."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", email="testuser@example.com", password="password")
        self.other_user = User.objects.create_user(username="otheruser", email="otheruser@example.com", password="password")

        # Create wallets for primary user
        self.wallet1 = Wallet.objects.create(user=self.user, name="Wallet 1", currency="USD", status=Wallet.Status.ACTIVE)
        self.wallet2 = Wallet.objects.create(user=self.user, name="Wallet 2", currency="USD", status=Wallet.Status.ACTIVE)
        self.wallet3 = Wallet.objects.create(user=self.user, name="Wallet 3", currency="USD", status=Wallet.Status.ACTIVE)

        # Create wallet for other user
        self.other_wallet = Wallet.objects.create(user=self.other_user, name="Other Wallet", currency="USD", status=Wallet.Status.ACTIVE)

        # Helper to create transactions
        self._setup_transactions()

    def _create_system_wallet(self, currency="USD", name="EQUITY"):
        system_user, _ = User.objects.get_or_create(
            username="SYSTEM",
            defaults={
                "email": "system@digitalwallet.local",
                "is_active": False,
                "is_system": True
            }
        )
        return Wallet.objects.get_or_create(
            user=system_user,
            name=name,
            currency=currency,
            status=Wallet.Status.ACTIVE
        )[0]

    def _create_funding_transaction(self, target_wallet, amount, description="Funding"):
        """Create a funding transaction from system wallet to target."""
        system_wallet = self._create_system_wallet(currency=target_wallet.currency)
        # System wallets can carry negative balance, no pre-seeding needed.
        txn = Transaction.objects.create(user=target_wallet.user, description=description)
        LedgerPosting.objects.create(
            transaction=txn,
            wallet=system_wallet,
            amount=amount,
            direction=LedgerPosting.Direction.DEBIT,
            currency=target_wallet.currency
        )
        LedgerPosting.objects.create(
            transaction=txn,
            wallet=target_wallet,
            amount=amount,
            direction=LedgerPosting.Direction.CREDIT,
            currency=target_wallet.currency
        )
        return txn

    def _create_transfer_transaction(self, from_wallet, to_wallet, amount, description="Transfer"):
        txn = Transaction.objects.create(user=from_wallet.user, description=description)
        LedgerPosting.objects.create(
            transaction=txn,
            wallet=from_wallet,
            amount=amount,
            direction=LedgerPosting.Direction.DEBIT,
            currency=from_wallet.currency
        )
        LedgerPosting.objects.create(
            transaction=txn,
            wallet=to_wallet,
            amount=amount,
            direction=LedgerPosting.Direction.CREDIT,
            currency=to_wallet.currency
        )
        return txn

    def _setup_transactions(self):
        """Create several transactions for testing."""
        self.txn1 = self._create_funding_transaction(self.wallet1, Decimal("100.00"), "Fund Wallet 1")
        # Verify transaction belongs to self.user
        self.assertEqual(self.txn1.user_id, self.user.id)
        self.txn2 = self._create_transfer_transaction(self.wallet1, self.wallet2, Decimal("30.00"), "Transfer to Wallet 2")
        self.assertEqual(self.txn2.user_id, self.user.id)
        self.txn3 = self._create_funding_transaction(self.wallet2, Decimal("50.00"), "Fund Wallet 2")
        self.assertEqual(self.txn3.user_id, self.user.id)
        self.txn4 = self._create_transfer_transaction(self.wallet2, self.wallet3, Decimal("20.00"), "Transfer to Wallet 3")
        self.assertEqual(self.txn4.user_id, self.user.id)

        # Other user's transaction
        self.other_txn = self._create_funding_transaction(self.other_wallet, Decimal("200.00"), "Other user fund")
        self.assertEqual(self.other_txn.user_id, self.other_user.id)

    def _get_auth_headers(self, user):
        """Generate HTTP Authorization header with JWT token."""
        token = create_access_token(user.id)
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_list_transactions_unauthenticated(self):
        """Unauthenticated requests should return 401."""
        response = self.client.get("/api/transactions/")
        self.assertEqual(response.status_code, 401)

    def test_list_transactions_empty_when_no_transactions(self):
        """User with no transactions should receive empty items array."""
        empty_user = User.objects.create_user(username="emptyuser", email="emptyuser@example.com", password="password")
        headers = self._get_auth_headers(empty_user)
        response = self.client.get("/api/transactions/", **headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['items'], [])
        self.assertEqual(data['count'], 0)
        self.assertEqual(data['total_pages'], 0)
        self.assertEqual(data['page'], 1)

    def test_list_transactions_returns_user_transactions(self):
        """Should return all transactions belonging to the user, ordered by created_at DESC."""
        headers = self._get_auth_headers(self.user)
        response = self.client.get("/api/transactions/", **headers)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        # Check pagination structure
        self.assertIn('items', data)
        self.assertIn('count', data)
        self.assertIn('page', data)
        self.assertIn('page_size', data)
        self.assertIn('total_pages', data)

        items = data['items']
        self.assertEqual(len(items), 4)  # txn1, txn2, txn3, txn4
        self.assertEqual(data['count'], 4)
        self.assertEqual(data['page'], 1)
        self.assertEqual(data['total_pages'], 1)

        # Check ordering: newest first
        timestamps = [item['created_at'] for item in items]
        # Should be descending
        self.assertEqual(timestamps, sorted(timestamps, reverse=True))

        # Verify each has required fields including postings
        for item in items:
            self.assertIn('id', item)
            self.assertIn('type', item)
            self.assertIn('description', item)
            self.assertIn('created_at', item)
            self.assertIn('reversal_of', item)  # should be None or UUID
            self.assertIn('postings', item)
            self.assertIsInstance(item['postings'], list)
            # Each transaction should have 2 postings
            self.assertEqual(len(item['postings']), 2)
            for posting in item['postings']:
                self.assertIn('wallet_id', posting)
                self.assertIn('wallet_name', posting)
                self.assertIn('wallet_currency', posting)
                self.assertIn('amount', posting)
                self.assertIn('direction', posting)
                self.assertIn('currency', posting)

    def test_list_transactions_excludes_other_users(self):
        """User should not see other users' transactions."""
        headers = self._get_auth_headers(self.user)
        response = self.client.get("/api/transactions/", **headers)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        items = data['items']
        returned_ids = {item['id'] for item in items}
        self.assertNotIn(str(self.other_txn.id), returned_ids)

    def test_list_transactions_filter_by_wallet(self):
        """Filtering by wallet_id should return only transactions involving that wallet."""
        headers = self._get_auth_headers(self.user)

        # Filter for wallet1: txn1 (CREDIT) and txn2 (DEBIT)
        response = self.client.get(f"/api/transactions/?wallet_id={self.wallet1.id}", **headers)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        items = data['items']
        self.assertEqual(len(items), 2)
        returned_ids = {item['id'] for item in items}
        self.assertIn(str(self.txn1.id), returned_ids)
        self.assertIn(str(self.txn2.id), returned_ids)
        self.assertNotIn(str(self.txn3.id), returned_ids)
        self.assertNotIn(str(self.txn4.id), returned_ids)

    def test_list_transactions_filter_by_wallet_invalid_uuid(self):
        """Invalid wallet_id should return 422 (validation error)."""
        headers = self._get_auth_headers(self.user)
        response = self.client.get("/api/transactions/?wallet_id=invalid-uuid", **headers)
        self.assertEqual(response.status_code, 422)

    def test_list_transactions_filter_by_wallet_not_owned(self):
        """Filtering by wallet that doesn't belong to user should return 400."""
        headers = self._get_auth_headers(self.user)
        response = self.client.get(f"/api/transactions/?wallet_id={self.other_wallet.id}", **headers)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Wallet not found or access denied", response.json()['detail'])

    def test_get_transaction_details_success(self):
        """Should return full transaction details including postings."""
        from apps.ledger.repository import LedgerRepository
        from apps.ledger.services.transaction_selector import get_transaction_details
        from apps.common.exceptions import LedgerError

        # Test with UUID object
        try:
            txn_repo = LedgerRepository.get_transaction_with_postings(self.txn1.id, self.user.id)
        except Transaction.DoesNotExist:
            self.fail("Repository failed to find transaction with UUID user_id")
        # Test with string version (what comes from JWT)
        user_id_str = str(self.user.id)
        try:
            txn_repo_str = LedgerRepository.get_transaction_with_postings(self.txn1.id, user_id_str)
        except Transaction.DoesNotExist:
            self.fail("Repository failed to find transaction with string user_id")

        # Test selector function with a mock auth object (simulating request.auth)
        class MockAuth:
            def __init__(self, user):
                self.id = str(user.id)

        mock_auth = MockAuth(self.user)
        try:
            txn_sel = get_transaction_details(mock_auth, self.txn1.id)
        except LedgerError:
            self.fail("Selector failed to find transaction")

        headers = self._get_auth_headers(self.user)
        response = self.client.get(f"/api/transactions/{self.txn1.id}", **headers)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data['id'], str(self.txn1.id))
        self.assertEqual(data['type'], "normal")
        self.assertEqual(data['description'], "Fund Wallet 1")
        self.assertIn('postings', data)
        self.assertEqual(len(data['postings']), 2)

        # Verify posting structure
        posting1, posting2 = data['postings']
        # Check each posting has required fields
        for posting in data['postings']:
            self.assertIn('wallet_id', posting)
            self.assertIn('wallet_name', posting)
            self.assertIn('wallet_currency', posting)
            self.assertIn('amount', posting)
            self.assertIn('direction', posting)
            self.assertIn('currency', posting)

        # Verify wallet details
        wallet_ids = {p['wallet_id'] for p in data['postings']}
        self.assertEqual(len(wallet_ids), 2)

    def test_get_transaction_details_not_found(self):
        """Should return 404 for transaction that doesn't exist or not owned by user."""
        headers = self._get_auth_headers(self.user)

        fake_id = "00000000-0000-0000-0000-000000000000"
        response = self.client.get(f"/api/transactions/{fake_id}", **headers)
        self.assertEqual(response.status_code, 404)

    def test_get_transaction_details_other_user(self):
        """Should return 404 when trying to access another user's transaction."""
        headers = self._get_auth_headers(self.user)
        response = self.client.get(f"/api/transactions/{self.other_txn.id}", **headers)
        self.assertEqual(response.status_code, 404)

    def test_transaction_with_reversal(self):
        """Test that reversal transactions are properly represented."""
        # Create a reversal transaction manually
        reversal_txn = Transaction.objects.create(
            user=self.user,
            description="Reversal",
            type=Transaction.TransactionType.REVERSAL,
            reversal_of=self.txn1
        )
        # Copy postings with opposite signs
        for posting in self.txn1.postings.all():
            LedgerPosting.objects.create(
                transaction=reversal_txn,
                wallet=posting.wallet,
                amount=-posting.amount,
                direction=LedgerPosting.Direction.CREDIT if posting.direction == LedgerPosting.Direction.DEBIT else LedgerPosting.Direction.DEBIT,
                currency=posting.currency
            )

        headers = self._get_auth_headers(self.user)
        response = self.client.get(f"/api/transactions/{reversal_txn.id}", **headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['type'], "reversal")
        self.assertEqual(data['reversal_of'], str(self.txn1.id))

        # Also check it appears in list
        list_response = self.client.get("/api/transactions/", **headers)
        list_data = list_response.json()
        items = list_data['items']
        reversal_items = [item for item in items if item['id'] == str(reversal_txn.id)]
        self.assertEqual(len(reversal_items), 1)
        self.assertEqual(reversal_items[0]['type'], "reversal")
        self.assertEqual(reversal_items[0]['reversal_of'], str(self.txn1.id))

    def test_pagination_default_page_size(self):
        """Default page size should be 20."""
        headers = self._get_auth_headers(self.user)
        response = self.client.get("/api/transactions/", **headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['page_size'], 20)
        # Should have 4 items, all on page 1
        self.assertEqual(len(data['items']), 4)
        self.assertEqual(data['count'], 4)
        self.assertEqual(data['total_pages'], 1)

    def test_pagination_custom_page_size(self):
        """Should respect custom page_size parameter."""
        headers = self._get_auth_headers(self.user)
        response = self.client.get("/api/transactions/?page_size=2", **headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['page_size'], 2)
        self.assertEqual(len(data['items']), 2)
        self.assertEqual(data['count'], 4)
        self.assertEqual(data['total_pages'], 2)

    def test_pagination_page_2(self):
        """Should return correct items for page 2."""
        headers = self._get_auth_headers(self.user)
        response = self.client.get("/api/transactions/?page=2&page_size=2", **headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['page'], 2)
        self.assertEqual(len(data['items']), 2)
        # Items should be the older ones (since order is newest first)
        # Page 1 has txn4, txn3 (newest)
        # Page 2 should have txn2, txn1
        item_ids = {item['id'] for item in data['items']}
        self.assertIn(str(self.txn2.id), item_ids)
        self.assertIn(str(self.txn1.id), item_ids)

    def test_pagination_max_page_size_limit(self):
        """Page size should be capped at 100 or return error."""
        headers = self._get_auth_headers(self.user)
        response = self.client.get("/api/transactions/?page_size=101", **headers)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Page size must be between 1 and 100", response.json()['detail'])

    def test_pagination_invalid_page(self):
        """Page must be >= 1."""
        headers = self._get_auth_headers(self.user)
        response = self.client.get("/api/transactions/?page=0", **headers)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Page must be >= 1", response.json()['detail'])

    def test_pagination_postings_included(self):
        """Each transaction in list should include complete posting details."""
        headers = self._get_auth_headers(self.user)
        response = self.client.get("/api/transactions/?page_size=1", **headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        item = data['items'][0]
        self.assertIn('postings', item)
        self.assertEqual(len(item['postings']), 2)
        # Verify posting structure
        for posting in item['postings']:
            self.assertIn('wallet_id', posting)
            self.assertIn('wallet_name', posting)
            self.assertIn('wallet_currency', posting)
            self.assertIn('amount', posting)
            self.assertIn('direction', posting)
            self.assertIn('currency', posting)
            # Amount should be Decimal string or numeric
            self.assertIsNotNone(posting['amount'])
            self.assertIn(posting['direction'], ['debit', 'credit'])

    def test_pagination_filtered_by_wallet_includes_postings(self):
        """Filtered transactions should also include posting details."""
        headers = self._get_auth_headers(self.user)
        response = self.client.get(f"/api/transactions/?wallet_id={self.wallet1.id}&page_size=10", **headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        items = data['items']
        self.assertEqual(len(items), 2)
        for item in items:
            self.assertIn('postings', item)
            self.assertGreater(len(item['postings']), 0)
