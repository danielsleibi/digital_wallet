# apps/ledger/services/transaction_selector.py

"""
Read-only transaction query operations.

This module separates query concerns from transaction_service.py
which handles write operations (create, reverse, refund).
"""

from typing import List
from uuid import UUID

from django.db.models import QuerySet

from apps.ledger.repository import LedgerRepository
from apps.ledger.models import Transaction
from apps.wallets.repository import WalletRepository
from apps.common.exceptions import LedgerError
from apps.users.repository import UserRepository


def get_user_transactions(user, limit=None, offset=None) -> QuerySet[Transaction]:
    """
    Retrieve all transactions for the authenticated user.

    Args:
        user: DomainUser (from JWT auth) or Django User instance.
        limit: Maximum number of transactions to return (optional)
        offset: Number of transactions to skip (optional, for pagination)

    Returns:
        QuerySet[Transaction]: Transactions belonging to the user, ordered by created_at DESC.
    """
    return LedgerRepository.get_user_transactions(user.id, limit=limit, offset=offset)


def get_user_transactions_by_wallet(user, wallet_id: UUID, limit=None, offset=None) -> QuerySet[Transaction]:
    """
    Retrieve all transactions for a specific wallet belonging to the authenticated user.

    Args:
        user: DomainUser (from JWT auth) or Django User instance.
        wallet_id: UUID of the wallet to filter by.
        limit: Maximum number of transactions to return (optional)
        offset: Number of transactions to skip (optional, for pagination)

    Returns:
        QuerySet[Transaction]: Transactions involving the wallet, ordered by created_at DESC.

    Raises:
        LedgerError: If the wallet does not exist, is inactive, or doesn't belong to the user.
    """
    # Validate wallet ownership first
    try:
        WalletRepository.get_user_wallet(wallet_id, user.id)
    except Exception:
        raise LedgerError("Wallet not found or access denied")

    return LedgerRepository.get_wallet_transactions(wallet_id, user.id, limit=limit, offset=offset)


def get_transaction_details(user, transaction_id: UUID) -> Transaction:
    """
    Retrieve a single transaction with its postings and wallet details.

    Args:
        user: DomainUser (from JWT auth) or Django User instance.
        transaction_id: UUID of the transaction to retrieve.

    Returns:
        Transaction: Transaction instance with postings prefetched (including wallet data).

    Raises:
        LedgerError: If the transaction does not exist or does not belong to the user.
    """
    try:
        return LedgerRepository.get_transaction_with_postings(transaction_id, user.id)
    except Transaction.DoesNotExist:
        raise LedgerError("Transaction not found or access denied")
