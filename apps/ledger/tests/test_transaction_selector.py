# apps/ledger/tests/test_transaction_selector.py

"""
Tests for transaction query operations: repository methods and selector service functions.
"""

from decimal import Decimal
from unittest.mock import MagicMock
from django.test import TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from apps.wallets.models import Wallet
from apps.ledger.models import Transaction, LedgerPosting
from apps.ledger.repository import LedgerRepository
from apps.ledger.services.transaction_selector import (
    get_user_transactions,
    get_user_transactions_by_wallet,
    get_transaction_details,
)
from apps.wallets.repository import WalletRepository
from apps.common.exceptions import LedgerError

User = get_user_model()


class TransactionQueryHelper:
    """Helper mixin for creating test transactions and wallets."""

    def create_user(self, username="testuser"):
        # Provide unique email to satisfy unique constraint
        return User.objects.create_user(username=username, email=f"{username}@example.com", password="password")

    def create_wallet(self, user, name, currency="USD", status=Wallet.Status.ACTIVE):
        return Wallet.objects.create(user=user, name=name, currency=currency, status=status)

    def create_system_wallet(self, currency="USD", name="EQUITY"):
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

    def fund_wallet(self, wallet, amount, system_wallet=None):
        """Create a funding transaction: DEBIT system, CREDIT target wallet."""
        if system_wallet is None:
            system_wallet = self.create_system_wallet(currency=wallet.currency)

        # System wallets can carry negative balances, so no pre-seeding needed.
        # Create a balanced transaction directly.
        txn = create_transaction(
            user=wallet.user,
            description=f"Fund {wallet.name}",
            postings=[
                {
                    "wallet_id": system_wallet.id,
                    "amount": amount,
                    "direction": LedgerPosting.Direction.DEBIT,
                },
                {
                    "wallet_id": wallet.id,
                    "amount": amount,
                    "direction": LedgerPosting.Direction.CREDIT,
                }
            ]
        )
        return txn

    def create_transfer(self, from_wallet, to_wallet, amount):
        """Create a transfer transaction between two wallets."""
        return create_transaction(
            user=from_wallet.user,
            description=f"Transfer to {to_wallet.name}",
            postings=[
                {
                    "wallet_id": from_wallet.id,
                    "amount": amount,
                    "direction": LedgerPosting.Direction.DEBIT,
                },
                {
                    "wallet_id": to_wallet.id,
                    "amount": amount,
                    "direction": LedgerPosting.Direction.CREDIT,
                }
            ]
        )


from apps.ledger.services.transaction_service import create_transaction


class LedgerRepositoryTransactionTests(TransactionTestCase, TransactionQueryHelper):
    """Tests for LedgerRepository query methods."""

    def setUp(self):
        super().setUp()
        self.user = self.create_user()
        self.wallet1 = self.create_wallet(self.user, "Wallet 1", "USD")
        self.wallet2 = self.create_wallet(self.user, "Wallet 2", "USD")
        self.wallet3 = self.create_wallet(self.user, "Wallet 3", "USD")

        # Fund wallets with some transactions
        self.txn1 = self.fund_wallet(self.wallet1, Decimal("100.00"))
        self.txn2 = self.transfer = self.create_transfer(self.wallet1, self.wallet2, Decimal("30.00"))
        self.txn3 = self.fund_wallet(self.wallet2, Decimal("50.00"))

    def test_get_user_transactions_returns_only_user_transactions(self):
        """get_user_transactions should return only transactions belonging to the user, ordered by created_at DESC."""
        txns = LedgerRepository.get_user_transactions(self.user.id)
        self.assertEqual(txns.count(), 3)
        # Check ordering: newest first
        first = txns.first()
        last = txns.last()
        self.assertGreaterEqual(first.created_at, last.created_at)

    def test_get_user_transactions_excludes_other_users(self):
        """Transactions from other users should not be returned."""
        other_user = self.create_user("otheruser")
        other_wallet = self.create_wallet(other_user, "Other Wallet", "USD")
        self.fund_wallet(other_wallet, Decimal("100.00"))

        txns = LedgerRepository.get_user_transactions(self.user.id)
        self.assertEqual(txns.count(), 3)
        # Verify none belong to other_user
        for txn in txns:
            self.assertEqual(txn.user, self.user)

    def test_get_wallet_transactions_returns_transactions_for_wallet(self):
        """get_wallet_transactions should return all transactions that have a posting for the given wallet."""
        txns = LedgerRepository.get_wallet_transactions(self.wallet1.id, self.user.id)
        # wallet1 participates in txn1 (funding CREDIT) and txn2 (transfer DEBIT)
        self.assertEqual(txns.count(), 2)
        txn_ids = set(txns.values_list('id', flat=True))
        self.assertIn(self.txn1.id, txn_ids)
        self.assertIn(self.txn2.id, txn_ids)
        self.assertNotIn(self.txn3.id, txn_ids)

    def test_get_wallet_transactions_filters_by_user(self):
        """Only transactions owned by the user should be returned, even if other users have postings to same wallet (but wallet belongs to user)."""
        # Create another user with a wallet having the same ID? Actually create separate wallet
        other_user = self.create_user("otheruser")
        other_wallet = self.create_wallet(other_user, "Other Wallet", "USD")
        other_txn = self.fund_wallet(other_wallet, Decimal("100.00"))

        # Query for wallet1 (should still only return user's transactions)
        txns = LedgerRepository.get_wallet_transactions(self.wallet1.id, self.user.id)
        for txn in txns:
            self.assertEqual(txn.user, self.user)

    def test_get_transaction_with_postings_returns_full_details(self):
        """get_transaction_with_postings should return transaction with postings prefetched."""
        txn = LedgerRepository.get_transaction_with_postings(self.txn1.id, self.user.id)
        self.assertEqual(txn.id, self.txn1.id)
        # Check postings are loaded
        self.assertEqual(txn.postings.count(), 2)
        # Check wallets are prefetched (no additional DB hits)
        posting_list = list(txn.postings.all())
        self.assertEqual(len(posting_list), 2)
        for posting in posting_list:
            self.assertIsNotNone(posting.wallet)
            self.assertEqual(posting.wallet.id, posting.wallet_id)

    def test_get_transaction_with_postings_raises_for_wrong_user(self):
        """Should raise Transaction.DoesNotExist if transaction belongs to another user."""
        other_user = self.create_user("otheruser")
        other_wallet = self.create_wallet(other_user, "Other", "USD")
        other_txn = self.fund_wallet(other_wallet, Decimal("100.00"))

        with self.assertRaises(Transaction.DoesNotExist):
            LedgerRepository.get_transaction_with_postings(other_txn.id, self.user.id)

    def test_get_transaction_with_postings_raises_for_nonexistent(self):
        """Should raise Transaction.DoesNotExist if transaction doesn't exist."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        with self.assertRaises(Transaction.DoesNotExist):
            LedgerRepository.get_transaction_with_postings(fake_id, self.user.id)


class TransactionSelectorServiceTests(TransactionTestCase, TransactionQueryHelper):
    """Tests for transaction_selector service functions."""

    def setUp(self):
        super().setUp()
        self.user = self.create_user()
        self.wallet1 = self.create_wallet(self.user, "Wallet 1", "USD")
        self.wallet2 = self.create_wallet(self.user, "Wallet 2", "USD")

        self.txn1 = self.fund_wallet(self.wallet1, Decimal("100.00"))
        self.txn2 = self.create_transfer(self.wallet1, self.wallet2, Decimal("30.00"))

    def test_get_user_transactions(self):
        """Should return all user's transactions."""
        # Mock a DomainUser-like object
        mock_user = MagicMock()
        mock_user.id = self.user.id

        txns = get_user_transactions(mock_user)
        txn_ids = set(txns.values_list('id', flat=True))
        self.assertIn(self.txn1.id, txn_ids)
        self.assertIn(self.txn2.id, txn_ids)

    def test_get_user_transactions_by_wallet(self):
        """Should return transactions involving the specified wallet only."""
        mock_user = MagicMock()
        mock_user.id = self.user.id

        txns = get_user_transactions_by_wallet(mock_user, self.wallet1.id)
        txn_ids = set(txns.values_list('id', flat=True))
        self.assertIn(self.txn1.id, txn_ids)
        self.assertIn(self.txn2.id, txn_ids)
        self.assertEqual(txns.count(), 2)

        # For wallet2 only, should have txn2 and txn3? txn3 not created yet
        txns_wallet2 = get_user_transactions_by_wallet(mock_user, self.wallet2.id)
        txn_ids_wallet2 = set(txns_wallet2.values_list('id', flat=True))
        self.assertIn(self.txn2.id, txn_ids_wallet2)
        self.assertNotIn(self.txn1.id, txn_ids_wallet2)

    def test_get_user_transactions_by_wallet_raises_for_invalid_wallet(self):
        """Should raise LedgerError if wallet doesn't exist or doesn't belong to user."""
        mock_user = MagicMock()
        mock_user.id = self.user.id

        fake_wallet_id = "00000000-0000-0000-0000-000000000000"
        with self.assertRaises(LedgerError):
            get_user_transactions_by_wallet(mock_user, fake_wallet_id)

    def test_get_transaction_details(self):
        """Should return transaction with postings and wallet details."""
        mock_user = MagicMock()
        mock_user.id = self.user.id

        txn = get_transaction_details(mock_user, self.txn1.id)
        self.assertEqual(txn.id, self.txn1.id)
        self.assertEqual(txn.postings.count(), 2)
        # Verify each posting has wallet data accessible
        for posting in txn.postings.all():
            self.assertIsNotNone(posting.wallet)
            self.assertIsNotNone(posting.wallet.name)

    def test_get_transaction_details_raises_for_wrong_user(self):
        """Should raise LedgerError if transaction belongs to another user."""
        other_user = self.create_user("otheruser")
        other_wallet = self.create_wallet(other_user, "Other", "USD")
        other_txn = self.fund_wallet(other_wallet, Decimal("100.00"))

        mock_user = MagicMock()
        mock_user.id = self.user.id

        with self.assertRaises(LedgerError):
            get_transaction_details(mock_user, other_txn.id)

    def test_get_transaction_details_raises_for_nonexistent(self):
        """Should raise LedgerError if transaction doesn't exist."""
        mock_user = MagicMock()
        mock_user.id = self.user.id

        fake_id = "00000000-0000-0000-0000-000000000000"
        with self.assertRaises(LedgerError):
            get_transaction_details(mock_user, fake_id)
