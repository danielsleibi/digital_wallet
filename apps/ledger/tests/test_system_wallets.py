from decimal import Decimal
from django.test import TransactionTestCase
from django.contrib.auth import get_user_model
from apps.wallets.models import Wallet
from apps.ledger.models import LedgerPosting, Transaction
from apps.ledger.services.transaction_service import create_transaction
from apps.ledger.services.compensation_service import reverse_transaction, refund_transaction
from apps.common.exceptions import InsufficientFundsError

User = get_user_model()

class SystemWalletTests(TransactionTestCase):
    def setUp(self):
        self.system_user, _ = User.objects.get_or_create(
            username="SYSTEM",
            defaults={
                "email": "system@digitalwallet.local",
                "is_active": False,
                "is_system": True
            }
        )
        
        self.equity_wallet, _ = Wallet.objects.get_or_create(
            user=self.system_user,
            name="EQUITY",
            currency="USD",
            defaults={"status": Wallet.Status.ACTIVE}
        )
        
        # Create a standard user and wallet
        self.user = User.objects.create_user(username="testuser", password="password")
        self.user_wallet = Wallet.objects.create(
            user=self.user,
            name="My Wallet",
            currency="USD",
            status=Wallet.Status.ACTIVE
        )

    def test_system_wallet_can_carry_negative_balance(self):
        amount = Decimal("1000.00")
        
        # Start a transaction where SYSTEM::EQUITY is debited for 1000 USD
        # Normally this would throw InsufficientFundsError as EQUITY starts with 0 USD
        txn = create_transaction(
            user=self.user,
            description="Initial Funding",
            postings=[
                {
                    "wallet_id": self.equity_wallet.id,
                    "amount": amount,
                    "direction": LedgerPosting.Direction.DEBIT,
                },
                {
                    "wallet_id": self.user_wallet.id,
                    "amount": amount,
                    "direction": LedgerPosting.Direction.CREDIT,
                }
            ]
        )
        
        self.assertIsNotNone(txn)
        
        # User wallet positive
        self.assertEqual(self._get_balance(self.user_wallet), Decimal("1000.00"))
        
        # System wallet negative
        self.assertEqual(self._get_balance(self.equity_wallet), Decimal("-1000.00"))

    def test_user_wallet_still_enforces_positive_balance(self):
        # Ensure that standard users still follow FR-14
        amount = Decimal("50.00")
        
        with self.assertRaisesMessage(InsufficientFundsError, "Insufficient funds"):
            create_transaction(
                user=self.user,
                description="Failed Outflow",
                postings=[
                    {
                        "wallet_id": self.user_wallet.id,
                        "amount": amount,
                        "direction": LedgerPosting.Direction.DEBIT,
                    },
                    {
                        "wallet_id": self.equity_wallet.id,
                        "amount": amount,
                        "direction": LedgerPosting.Direction.CREDIT,
                    }
                ]
            )

    def test_reverse_transaction_with_system_wallet_negative_balance(self):
        """
        Test that reversing a transaction works correctly when the system wallet
        has a negative balance and the reversal would further debit it (making it more negative).
        System wallets should be allowed to carry any balance, positive or negative.
        """
        # Step 1: Create a transaction that gives system wallet a negative balance
        # Debit system wallet (makes it negative), credit user wallet
        initial_amount = Decimal("1000.00")
        txn1 = create_transaction(
            user=self.user,
            description="Initial Funding",
            postings=[
                {
                    "wallet_id": self.equity_wallet.id,
                    "amount": initial_amount,
                    "direction": LedgerPosting.Direction.DEBIT,
                },
                {
                    "wallet_id": self.user_wallet.id,
                    "amount": initial_amount,
                    "direction": LedgerPosting.Direction.CREDIT,
                }
            ]
        )
        # System wallet should now be -1000
        self.assertEqual(self._get_balance(self.equity_wallet), Decimal("-1000.00"))
        self.assertEqual(self._get_balance(self.user_wallet), Decimal("1000.00"))

        # Step 2: Create a second transaction that credits the system wallet
        # This will bring the system wallet balance closer to zero (or positive)
        # Debit user wallet, credit system wallet
        second_amount = Decimal("600.00")
        txn2 = create_transaction(
            user=self.user,
            description="Second Transaction",
            postings=[
                {
                    "wallet_id": self.user_wallet.id,
                    "amount": second_amount,
                    "direction": LedgerPosting.Direction.DEBIT,
                },
                {
                    "wallet_id": self.equity_wallet.id,
                    "amount": second_amount,
                    "direction": LedgerPosting.Direction.CREDIT,
                }
            ]
        )
        # User wallet: 1000 - 600 = 400
        # System wallet: -1000 + 600 = -400
        self.assertEqual(self._get_balance(self.user_wallet), Decimal("400.00"))
        self.assertEqual(self._get_balance(self.equity_wallet), Decimal("-400.00"))

        # Step 3: Reverse the second transaction
        # Reversal would: Credit user wallet (600), Debit system wallet (600)
        # The system wallet currently has -400. If we check balance normally,
        # we'd see balance (-400) < required debit (600) and would raise InsufficientFundsError.
        # But system wallets should allow negative balances, so this should succeed.
        # After reversal: User wallet 400 + 600 = 1000, System wallet -400 - 600 = -1000
        reversal_txn = reverse_transaction(user=self.user, transaction_id=txn2.id)
        self.assertEqual(reversal_txn.type, Transaction.TransactionType.REVERSAL)
        self.assertEqual(reversal_txn.reversal_of, txn2)

        self.assertEqual(self._get_balance(self.user_wallet), Decimal("1000.00"))
        self.assertEqual(self._get_balance(self.equity_wallet), Decimal("-1000.00"))

    def test_refund_transaction_with_system_wallet_negative_balance(self):
        """
        Test that refunding a transaction works correctly when the system wallet
        has a negative balance and the refund would debit it.
        System wallets should be allowed to carry any balance, positive or negative.
        """
        # Step 1: Create initial transaction that makes system wallet negative
        initial_amount = Decimal("1000.00")
        txn1 = create_transaction(
            user=self.user,
            description="Initial Funding",
            postings=[
                {
                    "wallet_id": self.equity_wallet.id,
                    "amount": initial_amount,
                    "direction": LedgerPosting.Direction.DEBIT,
                },
                {
                    "wallet_id": self.user_wallet.id,
                    "amount": initial_amount,
                    "direction": LedgerPosting.Direction.CREDIT,
                }
            ]
        )
        self.assertEqual(self._get_balance(self.equity_wallet), Decimal("-1000.00"))

        # Step 2: Create second transaction that credits system wallet
        second_amount = Decimal("500.00")
        txn2 = create_transaction(
            user=self.user,
            description="Second Transaction",
            postings=[
                {
                    "wallet_id": self.user_wallet.id,
                    "amount": second_amount,
                    "direction": LedgerPosting.Direction.DEBIT,
                },
                {
                    "wallet_id": self.equity_wallet.id,
                    "amount": second_amount,
                    "direction": LedgerPosting.Direction.CREDIT,
                }
            ]
        )
        # System wallet: -1000 + 500 = -500
        self.assertEqual(self._get_balance(self.equity_wallet), Decimal("-500.00"))
        self.assertEqual(self._get_balance(self.user_wallet), Decimal("500.00"))

        # Step 3: Refund part of the second transaction (e.g., 300)
        refund_amount = Decimal("300.00")
        refund_txn = refund_transaction(
            user=self.user,
            transaction_id=txn2.id,
            refund_amount=refund_amount
        )
        # Refund proportions: 300/500 = 0.6
        # Refund postings:
        # - Debit user wallet for 0.6 * 500 = 300 (user gets money back, so user wallet increases)
        # - Credit system wallet for 0.6 * 500 = 300 (system loses money, so system wallet decreases)
        # Refund should reverse part of it: CREDIT user, DEBIT system
        # So user wallet: 500 + 300 = 800
        # System wallet: -500 - 300 = -800
        self.assertEqual(self._get_balance(self.user_wallet), Decimal("800.00"))
        self.assertEqual(self._get_balance(self.equity_wallet), Decimal("-800.00"))
            
    def _get_balance(self, wallet):
        from django.db.models import Sum
        return LedgerPosting.objects.filter(wallet=wallet).aggregate(total=Sum("amount"))["total"] or Decimal("0")

    def test_ledger_always_balanced(self):
        """
        Verify that the sum of all ledger posting amounts equals zero.
        This is the fundamental invariant of double-entry bookkeeping.
        Test with multiple transactions involving system wallets.
        """
        # Create another user wallet to involve multiple wallets
        user_wallet2 = Wallet.objects.create(
            user=self.user, name="Wallet 2", currency="USD", status=Wallet.Status.ACTIVE
        )

        # Transaction 1: System wallet debits 1000, user wallet credits 1000
        create_transaction(
            user=self.user,
            description="Funding via system",
            postings=[
                {"wallet_id": self.equity_wallet.id, "amount": Decimal("1000.00"), "direction": LedgerPosting.Direction.DEBIT},
                {"wallet_id": self.user_wallet.id, "amount": Decimal("1000.00"), "direction": LedgerPosting.Direction.CREDIT},
            ]
        )

        # Transaction 2: User wallet transfers 300 to user_wallet2
        create_transaction(
            user=self.user,
            description="Transfer to another wallet",
            postings=[
                {"wallet_id": self.user_wallet.id, "amount": Decimal("300.00"), "direction": LedgerPosting.Direction.DEBIT},
                {"wallet_id": user_wallet2.id, "amount": Decimal("300.00"), "direction": LedgerPosting.Direction.CREDIT},
            ]
        )

        # Transaction 3: System wallet credits 200 (from user_wallet2), user_wallet2 debits 200
        create_transaction(
            user=self.user,
            description="Fee-like transaction",
            postings=[
                {"wallet_id": user_wallet2.id, "amount": Decimal("200.00"), "direction": LedgerPosting.Direction.DEBIT},
                {"wallet_id": self.equity_wallet.id, "amount": Decimal("200.00"), "direction": LedgerPosting.Direction.CREDIT},
            ]
        )

        # Verify invariant: sum of all posting amounts should be zero
        from django.db.models import Sum
        total = LedgerPosting.objects.aggregate(total=Sum("amount"))["total"] or Decimal("0")
        self.assertEqual(total, Decimal("0.00"))
