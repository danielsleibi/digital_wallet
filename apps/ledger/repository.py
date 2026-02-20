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
    def create_transaction(*, user, description):
        """
        Persist a new Transaction row and return it.
        """
        return Transaction.objects.create(
            user=user,
            description=description,
        )

    @staticmethod
    def create_postings(posting_records):
        """
        Bulk-insert a list of LedgerPosting instances.

        Args:
            posting_records: list of LedgerPosting model instances
                             (unsaved, without pk).
        """
        return LedgerPosting.objects.bulk_create(posting_records)
