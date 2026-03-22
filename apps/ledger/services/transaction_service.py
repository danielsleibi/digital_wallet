# apps/ledger/services/transaction_service.py

from django.db import transaction
from decimal import Decimal
from apps.wallets.repository import WalletRepository
from apps.ledger.repository import LedgerRepository
from apps.ledger.models import LedgerPosting
from apps.common.exceptions import LedgerError, InsufficientFundsError, CurrencyMismatchError
from apps.users.repository import UserRepository

@transaction.atomic
def create_transaction(*, user, description, postings):
    if len(postings) < 2:
        raise LedgerError("Transaction must have at least two postings")


    wallet_ids = {p["wallet_id"] for p in postings}

    wallets = WalletRepository.get_wallets_for_update(wallet_ids, user.id)

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
            raise CurrencyMismatchError("Cross-currency transaction not allowed")

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
            if wallet.is_system:
                continue

            balance = LedgerRepository.get_wallet_balance(wallet)

            if balance < p["amount"]:
                raise InsufficientFundsError("Insufficient funds")

    txn = LedgerRepository.create_transaction(
        user=UserRepository.get_by_id(user.id),
        description=description,
    )

    posting_records = []
    for p in postings:
        sign = Decimal("1") if p["direction"] == LedgerPosting.Direction.CREDIT else Decimal("-1")
        posting_records.append(
            LedgerPosting(
                transaction=txn,
                wallet=wallet_map[p["wallet_id"]],
                amount=sign * p["amount"],
                direction=p["direction"],
                currency=currency,
            )
        )

    LedgerRepository.create_postings(posting_records)

    return txn
