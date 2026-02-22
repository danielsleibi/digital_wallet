# apps/ledger/services/compensation_service.py

from django.db import transaction
from decimal import Decimal
from apps.wallets.repository import WalletRepository
from apps.ledger.repository import LedgerRepository
from apps.ledger.models import LedgerPosting, Transaction
from apps.common.exceptions import LedgerError

@transaction.atomic
def reverse_transaction(*, user, transaction_id):
    original_txn = LedgerRepository.get_transaction_for_update(transaction_id)
    
    if original_txn.type != Transaction.TransactionType.NORMAL:
        raise LedgerError("Only NORMAL transactions can be reversed")
        
    if Transaction.objects.filter(reversal_of=original_txn, type=Transaction.TransactionType.REVERSAL).exists():
        raise LedgerError("Transaction has already been fully reversed")

    postings = LedgerRepository.get_postings_for_transaction(original_txn)
    
    wallet_ids = {p.wallet_id for p in postings}
    wallets = WalletRepository.get_wallets_for_update(wallet_ids, user)
    if wallets.count() != len(wallet_ids):
        raise LedgerError("Invalid or inactive wallet")
    wallet_map = {w.id: w for w in wallets}

    reversal_txn = LedgerRepository.create_transaction(
        user=user,
        description=f"Reversal of {original_txn.id}",
        type=Transaction.TransactionType.REVERSAL,
        reversal_of=original_txn
    )
    
    posting_records = []
    for p in postings:
        new_direction = (
            LedgerPosting.Direction.CREDIT 
            if p.direction == LedgerPosting.Direction.DEBIT 
            else LedgerPosting.Direction.DEBIT
        )
        
        new_amount = -p.amount
        
        if new_direction == LedgerPosting.Direction.DEBIT:
            wallet = wallet_map[p.wallet_id]
            balance = LedgerRepository.get_wallet_balance(wallet)
            if balance < abs(new_amount):
                raise LedgerError("Insufficient funds for reversal")

        posting_records.append(
            LedgerPosting(
                transaction=reversal_txn,
                wallet_id=p.wallet_id,
                amount=new_amount,
                direction=new_direction,
                currency=p.currency,
            )
        )

    LedgerRepository.create_postings(posting_records)
    return reversal_txn

@transaction.atomic
def refund_transaction(*, user, transaction_id, refund_amount):
    refund_amount = Decimal(str(refund_amount))
    if refund_amount <= 0:
        raise LedgerError("Refund amount must be positive")

    original_txn = LedgerRepository.get_transaction_for_update(transaction_id)
    
    if original_txn.type != Transaction.TransactionType.NORMAL:
        raise LedgerError("Only NORMAL transactions can be refunded")
        
    postings = LedgerRepository.get_postings_for_transaction(original_txn)
    
    original_volume = sum(p.amount for p in postings if p.amount > 0)
    
    already_refunded = LedgerRepository.get_total_refunded_amount(original_txn)
    
    if refund_amount > (original_volume - already_refunded):
        raise LedgerError("Refund amount exceeds remaining refundable amount")
        
    wallet_ids = {p.wallet_id for p in postings}
    wallets = WalletRepository.get_wallets_for_update(wallet_ids, user)
    if wallets.count() != len(wallet_ids):
        raise LedgerError("Invalid or inactive wallet")
    wallet_map = {w.id: w for w in wallets}
        
    refund_txn = LedgerRepository.create_transaction(
        user=user,
        description=f"Refund of {original_txn.id}",
        type=Transaction.TransactionType.REFUND,
        reversal_of=original_txn
    )

    ratio = refund_amount / original_volume
    
    posting_records = []
    for p in postings:
        new_direction = (
            LedgerPosting.Direction.CREDIT 
            if p.direction == LedgerPosting.Direction.DEBIT 
            else LedgerPosting.Direction.DEBIT
        )
        
        raw_new_amount = -p.amount * ratio
        new_amount = raw_new_amount.quantize(Decimal("0.000000"))
        
        if new_amount == 0:
            raise LedgerError("Refund amount too small to generate valid postings")

        posting_records.append(
            LedgerPosting(
                transaction=refund_txn,
                wallet_id=p.wallet_id,
                amount=new_amount,
                direction=new_direction,
                currency=p.currency,
            )
        )

    total_refund_debits = sum(abs(p.amount) for p in posting_records if p.direction == LedgerPosting.Direction.DEBIT)
    total_refund_credits = sum(p.amount for p in posting_records if p.direction == LedgerPosting.Direction.CREDIT)
    
    difference = total_refund_credits - total_refund_debits
    if difference != 0:
        credit_postings = [p for p in posting_records if p.direction == LedgerPosting.Direction.CREDIT]
        credit_postings[0].amount -= difference
        
    for p in posting_records:
        if p.direction == LedgerPosting.Direction.DEBIT:
            wallet = wallet_map[p.wallet_id]
            balance = LedgerRepository.get_wallet_balance(wallet)
            if balance < abs(p.amount):
                raise LedgerError("Insufficient funds for refund")

    LedgerRepository.create_postings(posting_records)
    return refund_txn
