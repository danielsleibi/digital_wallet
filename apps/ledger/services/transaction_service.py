# apps/ledger/services/transaction_service.py

from django.db import transaction
from django.db.models import Sum
from decimal import Decimal
from apps.wallets.models import Wallet
from apps.ledger.models import Transaction, LedgerPosting
from apps.common.exceptions import LedgerError

@transaction.atomic
def create_transaction(*, user, description, postings):
    if len(postings) < 2:
        raise LedgerError("Transaction must have at least two postings")

    wallet_ids = {p["wallet_id"] for p in postings}

    wallets = (
        Wallet.objects
        .select_for_update()
        .filter(id__in=wallet_ids, user=user, status=Wallet.Status.ACTIVE)
    )

    if wallets.count() != len(wallet_ids):
        raise LedgerError("Invalid or inactive wallet")

    wallet_map = {w.id: w for w in wallets}

    currency = None
    total_debits = Decimal("0")
    total_credits = Decimal("0")

    for p in postings:
        wallet = wallet_map[p["wallet_id"]]

        if currency is None:
            currency = wallet.currency
        elif wallet.currency != currency:
            raise LedgerError("Cross-currency transaction not allowed")

        amount = p["amount"]
        if amount <= 0:
            raise LedgerError("Amount must be positive")

        if p["direction"] == LedgerPosting.Direction.DEBIT:
            total_debits += amount
        else:
            total_credits += amount

    if total_debits != total_credits:
        raise LedgerError("Debits must equal credits")

    # Balance checks
    for p in postings:
        if p["direction"] == LedgerPosting.Direction.DEBIT:
            wallet = wallet_map[p["wallet_id"]]

            balance = (
                LedgerPosting.objects
                .filter(wallet=wallet)
                .aggregate(total=Sum("amount"))["total"]
                or Decimal("0")
            )

            if balance < p["amount"]:
                raise LedgerError("Insufficient funds")

    txn = Transaction.objects.create(
        user=user,
        description=description,
    )

    for p in postings:
        sign = Decimal("1") if p["direction"] == LedgerPosting.Direction.CREDIT else Decimal("-1")

        LedgerPosting.objects.create(
            transaction=txn,
            wallet=wallet_map[p["wallet_id"]],
            amount=sign * p["amount"],
            direction=p["direction"],
            currency=currency,
        )

    return txn
