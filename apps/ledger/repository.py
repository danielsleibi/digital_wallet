# apps/ledger/repository.py

from decimal import Decimal
from django.db.models import Sum
from apps.ledger.models import Transaction, LedgerPosting


class LedgerRepository:
    @staticmethod
    def get_wallet_balance(wallet):
        """
        Return the current balance of a wallet by summing all its postings.
        """
        return (
            LedgerPosting.objects
            .filter(wallet=wallet)
            .aggregate(total=Sum("amount"))["total"]
            or Decimal("0")
        )

    @staticmethod
    def create_transaction(*, user, description, type=Transaction.TransactionType.NORMAL, reversal_of=None):
        """
        Persist a new Transaction row and return it.
        """
        return Transaction.objects.create(
            user=user,
            description=description,
            type=type,
            reversal_of=reversal_of
        )

    @staticmethod
    def get_transaction_for_update(transaction_id):
        return Transaction.objects.select_for_update().get(id=transaction_id)

    @staticmethod
    def get_postings_for_transaction(transaction):
        return LedgerPosting.objects.filter(transaction=transaction)

    @staticmethod
    def get_total_refunded_amount(transaction):
        from django.db.models import Sum
        
        refund_txns = Transaction.objects.filter(
            reversal_of=transaction,
            type=Transaction.TransactionType.REFUND
        )
        # Sum the positive (CREDIT) amounts of the refund transactions
        total_refunded = LedgerPosting.objects.filter(
            transaction__in=refund_txns,
            amount__gt=0
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        
        return total_refunded

    @staticmethod
    def create_postings(posting_records):
        """
        Bulk-insert a list of LedgerPosting instances.

        Args:
            posting_records: list of LedgerPosting model instances
                             (unsaved, without pk).
        """
        return LedgerPosting.objects.bulk_create(posting_records)
