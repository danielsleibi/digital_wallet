from decimal import Decimal
from django.test import TransactionTestCase
from django.contrib.auth import get_user_model
from apps.wallets.models import Wallet
from apps.ledger.models import Transaction, LedgerPosting
from apps.ledger.services.transaction_service import create_transaction
from apps.ledger.services.compensation_service import reverse_transaction, refund_transaction
from apps.common.exceptions import TransactionReversalError, TransactionRefundError
from concurrent.futures import ThreadPoolExecutor

User = get_user_model()

class TransactionReversalRefundTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password")
        self.wallet1 = Wallet.objects.create(
            user=self.user, name="Wallet 1", currency="USD", status=Wallet.Status.ACTIVE
        )
        self.wallet2 = Wallet.objects.create(
            user=self.user, name="Wallet 2", currency="USD", status=Wallet.Status.ACTIVE
        )
        
        self._fund_wallet(self.wallet1, Decimal("1000.00"))
        
        # Create an initial transaction from Wallet 1 to Wallet 2 for testing
        self.original_txn = create_transaction(
            user=self.user,
            description="Initial Transfer",
            postings=[
                {"wallet_id": self.wallet1.id, "amount": Decimal("100.00"), "direction": LedgerPosting.Direction.DEBIT},
                {"wallet_id": self.wallet2.id, "amount": Decimal("100.00"), "direction": LedgerPosting.Direction.CREDIT},
            ]
        )

    def _fund_wallet(self, wallet, amount):
        system_wallet = Wallet.objects.create(
            user=self.user, name=f"System Fund {wallet.id}", currency=wallet.currency, status=Wallet.Status.ACTIVE
        )
        txn = Transaction.objects.create(user=self.user, description="Initial Funding")
        LedgerPosting.objects.create(
            transaction=txn, wallet=system_wallet, amount=Decimal("1000000"),
            direction=LedgerPosting.Direction.CREDIT, currency=wallet.currency
        )
        create_transaction(
            user=self.user, description="Fund Wallet",
            postings=[
                {"wallet_id": system_wallet.id, "amount": amount, "direction": LedgerPosting.Direction.DEBIT},
                {"wallet_id": wallet.id, "amount": amount, "direction": LedgerPosting.Direction.CREDIT}
            ]
        )

    def _get_balance(self, wallet):
        from apps.ledger.repository import LedgerRepository
        return LedgerRepository.get_wallet_balance(wallet)

    def test_reversal_success(self):
        rev_txn = reverse_transaction(user=self.user, transaction_id=self.original_txn.id)
        self.assertEqual(rev_txn.type, Transaction.TransactionType.REVERSAL)
        self.assertEqual(rev_txn.reversal_of, self.original_txn)
        
        # Original was: W1 -100, W2 +100
        # Reversal should be: W1 +100, W2 -100
        # So W1 balance goes from 900 to 1000. W2 goes from 100 to 0.
        self.assertEqual(self._get_balance(self.wallet1), Decimal("1000.00"))
        self.assertEqual(self._get_balance(self.wallet2), Decimal("0.00"))

    def test_prevent_reversal_of_reversal(self):
        rev_txn = reverse_transaction(user=self.user, transaction_id=self.original_txn.id)
        with self.assertRaises(TransactionReversalError):
            reverse_transaction(user=self.user, transaction_id=rev_txn.id)

    def test_prevent_duplicate_reversal(self):
        reverse_transaction(user=self.user, transaction_id=self.original_txn.id)
        with self.assertRaises(TransactionReversalError):
            reverse_transaction(user=self.user, transaction_id=self.original_txn.id)

    def test_refund_success(self):
        # Refund 40.00
        ref_txn = refund_transaction(user=self.user, transaction_id=self.original_txn.id, refund_amount=Decimal("40.00"))
        
        self.assertEqual(ref_txn.type, Transaction.TransactionType.REFUND)
        self.assertEqual(ref_txn.reversal_of, self.original_txn)
        
        # W1 balance: 900 + 40 = 940
        # W2 balance: 100 - 40 = 60
        self.assertEqual(self._get_balance(self.wallet1), Decimal("940.00"))
        self.assertEqual(self._get_balance(self.wallet2), Decimal("60.00"))
        
    def test_multiple_refunds(self):
        refund_transaction(user=self.user, transaction_id=self.original_txn.id, refund_amount=Decimal("40.00"))
        refund_transaction(user=self.user, transaction_id=self.original_txn.id, refund_amount=Decimal("60.00"))
        
        self.assertEqual(self._get_balance(self.wallet1), Decimal("1000.00"))
        self.assertEqual(self._get_balance(self.wallet2), Decimal("0.00"))

    def test_prevent_over_refunding(self):
        refund_transaction(user=self.user, transaction_id=self.original_txn.id, refund_amount=Decimal("80.00"))
        with self.assertRaises(TransactionRefundError):
            refund_transaction(user=self.user, transaction_id=self.original_txn.id, refund_amount=Decimal("30.00"))

    def test_concurrency_simultaneous_refunds(self):
        # Allow 40 refund, try two 80 concurrent refunds. Only one should pass.
        def run_refund():
            try:
                from django.db import connection
                connection.close()
                refund_transaction(user=self.user, transaction_id=self.original_txn.id, refund_amount=Decimal("80.00"))
                return True
            except TransactionRefundError:
                return False

        with ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(run_refund)
            f2 = executor.submit(run_refund)
            results = [f1.result(), f2.result()]

        self.assertEqual(sum(results), 1)
        # Total refunded is 80
        self.assertEqual(self._get_balance(self.wallet1), Decimal("980.00"))
        self.assertEqual(self._get_balance(self.wallet2), Decimal("20.00"))
