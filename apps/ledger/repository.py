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

    @staticmethod
    def get_user_transactions(user_id, limit=None, offset=0):
        """
        Return all transactions belonging to the user, ordered by creation date (newest first).
        Uses select_related and prefetch_related to efficiently fetch postings and wallet data.
        Optional pagination via limit/offset.

        Args:
            user_id: UUID or string (user identifier)
            limit: Maximum number of transactions to return (None = no limit)
            offset: Number of transactions to skip (for pagination)

        Returns:
            QuerySet[Transaction]: Transactions with prefetched postings and wallet data.
        """
        from uuid import UUID
        from django.db.models import Prefetch

        if isinstance(user_id, str):
            user_id = UUID(user_id)

        qs = (
            Transaction.objects
            .select_related('user')
            .prefetch_related(
                Prefetch(
                    'postings',
                    queryset=LedgerPosting.objects.select_related('wallet')
                )
            )
            .filter(user_id=user_id)
            .order_by('-created_at')
        )

        if limit is not None:
            qs = qs[offset:offset + limit]

        return qs

    @staticmethod
    def get_wallet_transactions(wallet_id, user_id, limit=None, offset=0):
        """
        Return all transactions that have postings for the given wallet, belonging to the user.
        Joins through LedgerPosting and filters by wallet_id and transaction.user.
        Ordered by creation date (newest first).
        Optional pagination via limit/offset.

        Args:
            wallet_id: UUID of the wallet
            user_id: UUID or string (user identifier)
            limit: Maximum number of transactions to return (None = no limit)
            offset: Number of transactions to skip (for pagination)

        Returns:
            QuerySet[Transaction]: Transactions with prefetched postings and wallet data.
        """
        from uuid import UUID
        from django.db.models import Prefetch

        if isinstance(user_id, str):
            user_id = UUID(user_id)

        qs = (
            Transaction.objects
            .select_related('user')
            .prefetch_related(
                Prefetch(
                    'postings',
                    queryset=LedgerPosting.objects.select_related('wallet')
                )
            )
            .filter(
                postings__wallet_id=wallet_id,
                user_id=user_id
            )
            .distinct()
            .order_by('-created_at')
        )

        if limit is not None:
            qs = qs[offset:offset + limit]

        return qs

    @staticmethod
    def get_transaction_with_postings(transaction_id, user_id):
        """
        Retrieve a single transaction with its postings and wallet data, verifying user ownership.
        Raises Transaction.DoesNotExist if not found or not owned by user.
        """
        from django.db.models import Prefetch
        from uuid import UUID
        # Normalize user_id to UUID if string
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        return (
            Transaction.objects
            .select_related('user')
            .prefetch_related(
                Prefetch(
                    'postings',
                    queryset=LedgerPosting.objects.select_related('wallet')
                )
            )
            .get(id=transaction_id, user_id=user_id)
        )
