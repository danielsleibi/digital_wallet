from decimal import Decimal
from django.test import TransactionTestCase
from django.contrib.auth import get_user_model
from django.db import transaction
from concurrent.futures import ThreadPoolExecutor
from apps.wallets.models import Wallet
from apps.ledger.models import Transaction, LedgerPosting
from apps.ledger.services.transaction_service import create_transaction
from apps.common.exceptions import LedgerError, InsufficientFundsError, CurrencyMismatchError

User = get_user_model()

class TransactionServiceTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password")
        self.wallet1 = Wallet.objects.create(
            user=self.user,
            name="Wallet 1",
            currency="USD",
            status=Wallet.Status.ACTIVE
        )
        self.wallet2 = Wallet.objects.create(
            user=self.user,
            name="Wallet 2",
            currency="USD",
            status=Wallet.Status.ACTIVE
        )
        self.wallet3 = Wallet.objects.create(
            user=self.user,
            name="Wallet 3",
            currency="USD",
            status=Wallet.Status.ACTIVE
        )

        # Fund wallet 1
        self._fund_wallet(self.wallet1, Decimal("100.00"))

    def _fund_wallet(self, wallet, amount):
        # Create a funding transaction (conceptually from "system")
        # For simplicity in this test, we just create a transaction with no source check or just use the service if possible
        # Since service requires balanced, let's create a "System" wallet or just manually create postings for funding
        # But to use service, we need balanced. Let's create a system wallet.
        system_wallet = Wallet.objects.create(
            user=self.user,
            name=f"System Fund {wallet.id}",
            currency=wallet.currency,
            status=Wallet.Status.ACTIVE
        )
        # We manually create postings to fund the system wallet first to follow rules? 
        # Actually proper way: just direct DB insert for setup if we want to bypass checks, 
        # or use a system wallet with infinite funds (not implemented).
        # Let's just create a transaction from System to Wallet 1.
        # But system wallet needs funds? No, if we don't enforce balance on system wallet?
        # The service enforces balance on ALL wallets involved if they are debiting?
        # Service checks: "if balance < p['amount']: raise LedgerError".
        # So we need to fund the source.
        # Bypass: Manually create LedgerPosting for System Wallet with CREDIT direction? 
        # Wait, if we credit System Wallet, it has funds?
        # Debit reduces balance, Credit increases balance.
        # So to fund Wallet 1, we Debit System, Credit Wallet 1.
        # System needs balance to be debited.
        # Let's just insert a "deposit" posting for System Wallet manually via model to give it balance.
        
        # Funding the system wallet manually
        txn = Transaction.objects.create(user=self.user, description="Initial Funding")
        LedgerPosting.objects.create(
            transaction=txn,
            wallet=system_wallet,
            amount=Decimal("1000000"),
            direction=LedgerPosting.Direction.CREDIT,
            currency=wallet.currency
        )
        
        # Now use service to fund the target wallet
        create_transaction(
            user=self.user,
            description="Fund Wallet",
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

    def test_balanced_transaction_succeeds(self):
        amount = Decimal("50.00")
        create_transaction(
            user=self.user,
            description="Transfer",
            postings=[
                {
                    "wallet_id": self.wallet1.id,
                    "amount": amount,
                    "direction": LedgerPosting.Direction.DEBIT,
                },
                {
                    "wallet_id": self.wallet2.id,
                    "amount": amount,
                    "direction": LedgerPosting.Direction.CREDIT,
                }
            ]
        )
        
        # Verify balances
        w1_balance = self._get_balance(self.wallet1)
        w2_balance = self._get_balance(self.wallet2)
        
        self.assertEqual(w1_balance, Decimal("50.00")) # 100 - 50
        self.assertEqual(w2_balance, Decimal("50.00")) # 0 + 50

    def test_unbalanced_transaction_fails(self):
        with self.assertRaisesMessage(LedgerError, "Debits must equal credits"):
            create_transaction(
                user=self.user,
                description="Unbalanced",
                postings=[
                    {
                        "wallet_id": self.wallet1.id,
                        "amount": Decimal("50.00"),
                        "direction": LedgerPosting.Direction.DEBIT,
                    },
                    {
                        "wallet_id": self.wallet2.id,
                        "amount": Decimal("40.00"),
                        "direction": LedgerPosting.Direction.CREDIT,
                    }
                ]
            )

    def test_overspend_fails(self):
        with self.assertRaises(InsufficientFundsError):
            create_transaction(
                user=self.user,
                description="Overspend",
                postings=[
                    {
                        "wallet_id": self.wallet1.id,
                        "amount": Decimal("150.00"), # Balance is 100
                        "direction": LedgerPosting.Direction.DEBIT,
                    },
                    {
                        "wallet_id": self.wallet2.id,
                        "amount": Decimal("150.00"),
                        "direction": LedgerPosting.Direction.CREDIT,
                    }
                ]
            )

    def test_cross_currency_fails(self):
        eur_wallet = Wallet.objects.create(
            user=self.user,
            name="EUR Wallet",
            currency="EUR",
            status=Wallet.Status.ACTIVE
        )
        
        with self.assertRaises(CurrencyMismatchError):
            create_transaction(
                user=self.user,
                description="Cross Currency",
                postings=[
                    {
                        "wallet_id": self.wallet1.id,
                        "amount": Decimal("10.00"),
                        "direction": LedgerPosting.Direction.DEBIT,
                    },
                    {
                        "wallet_id": eur_wallet.id,
                        "amount": Decimal("10.00"),
                        "direction": LedgerPosting.Direction.CREDIT,
                    }
                ]
            )

    def test_concurrent_overspend_blocked(self):
        # Wallet 1 has 100. Try to spend 100 twice concurrently.
        amount = Decimal("100.00")
        
        def run_txn():
            try:
                # We need a new DB connection for each thread in Django tests
                from django.db import connection
                connection.close()
                create_transaction(
                    user=self.user,
                    description="Concurrent Transfer",
                    postings=[
                        {
                            "wallet_id": self.wallet1.id,
                            "amount": amount,
                            "direction": LedgerPosting.Direction.DEBIT,
                        },
                        {
                            "wallet_id": self.wallet2.id,
                            "amount": amount,
                            "direction": LedgerPosting.Direction.CREDIT,
                        }
                    ]
                )
                return True
            except InsufficientFundsError:
                return False

        with ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(run_txn)
            f2 = executor.submit(run_txn)
            
            results = [f1.result(), f2.result()]
            
        # Only one should succeed
        self.assertEqual(sum(results), 1)
        
        # Final balance check
        self.assertEqual(self._get_balance(self.wallet1), Decimal("0.00"))
        self.assertEqual(self._get_balance(self.wallet2), Decimal("100.00"))

    def test_reversal_restores_balance(self):
        # 1. Transfer 50 to Wallet 2
        amount = Decimal("50.00")
        create_transaction(
            user=self.user,
            description="Original Transfer",
            postings=[
                {
                    "wallet_id": self.wallet1.id,
                    "amount": amount,
                    "direction": LedgerPosting.Direction.DEBIT,
                },
                {
                    "wallet_id": self.wallet2.id,
                    "amount": amount,
                    "direction": LedgerPosting.Direction.CREDIT,
                }
            ]
        )
        
        self.assertEqual(self._get_balance(self.wallet1), Decimal("50.00"))
        self.assertEqual(self._get_balance(self.wallet2), Decimal("50.00"))

        # 2. Reverse: Transfer 50 back from Wallet 2 to Wallet 1
        create_transaction(
            user=self.user,
            description="Reversal",
            postings=[
                {
                    "wallet_id": self.wallet2.id,
                    "amount": amount,
                    "direction": LedgerPosting.Direction.DEBIT,
                },
                {
                    "wallet_id": self.wallet1.id,
                    "amount": amount,
                    "direction": LedgerPosting.Direction.CREDIT,
                }
            ]
        )

        self.assertEqual(self._get_balance(self.wallet1), Decimal("100.00"))
        self.assertEqual(self._get_balance(self.wallet2), Decimal("0.00"))

    def test_negative_amount_fails(self):
        with self.assertRaisesMessage(LedgerError, "Amount must be positive"):
            create_transaction(
                user=self.user,
                description="Negative Amount",
                postings=[
                    {
                        "wallet_id": self.wallet1.id,
                        "amount": Decimal("-10.00"),
                        "direction": LedgerPosting.Direction.DEBIT,
                    },
                    {
                        "wallet_id": self.wallet2.id,
                        "amount": Decimal("-10.00"),
                        "direction": LedgerPosting.Direction.CREDIT,
                    }
                ]
            )

    def test_transaction_with_3_wallets_fee(self):
        # Transfer 50 from W1 to W2, with 5 fee to W3
        # Total debit from W1: 55
        # Credit W2: 50
        # Credit W3: 5
        
        create_transaction(
            user=self.user,
            description="Transfer with Fee",
            postings=[
                {
                    "wallet_id": self.wallet1.id,
                    "amount": Decimal("55.00"),
                    "direction": LedgerPosting.Direction.DEBIT,
                },
                {
                    "wallet_id": self.wallet2.id,
                    "amount": Decimal("50.00"),
                    "direction": LedgerPosting.Direction.CREDIT,
                },
                {
                    "wallet_id": self.wallet3.id,
                    "amount": Decimal("5.00"),
                    "direction": LedgerPosting.Direction.CREDIT,
                }
            ]
        )
        
        self.assertEqual(self._get_balance(self.wallet1), Decimal("45.00")) # 100 - 55
        self.assertEqual(self._get_balance(self.wallet2), Decimal("50.00"))
        self.assertEqual(self._get_balance(self.wallet3), Decimal("5.00"))

    def _get_balance(self, wallet):
        # Helper since service doesn't expose get balance directly in this file
        from django.db.models import Sum
        return LedgerPosting.objects.filter(wallet=wallet).aggregate(total=Sum("amount"))["total"] or Decimal("0")
