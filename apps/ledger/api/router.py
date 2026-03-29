from ninja import Router
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from uuid import UUID

from apps.ledger.services.compensation_service import reverse_transaction, refund_transaction
from apps.ledger.services.transaction_service import create_transaction
from apps.ledger.repository import LedgerRepository
from apps.ledger.services.transaction_selector import (
    get_user_transactions,
    get_user_transactions_by_wallet,
    get_transaction_details,
)
from apps.ledger.models import LedgerPosting, Transaction
from apps.ledger.api.schemas import (
    TransactionOut,
    TransactionListItem,
    TransactionPostingOut,
    ErrorOut,
    PaginatedTransactionResponse,
)
from apps.common.exceptions import LedgerError, InsufficientFundsError, CurrencyMismatchError
from django.http import HttpRequest
from apps.common.auth.bearer import JWTAuth
from decimal import Decimal

router = Router(tags=["Transactions"])


@router.get("/", response={200: PaginatedTransactionResponse, 400: ErrorOut}, auth=JWTAuth())
def list_transactions(
    request: HttpRequest,
    wallet_id: Optional[UUID] = None,
    page: int = 1,
    page_size: int = 20
):
    """
    List transactions for the authenticated user with pagination.

    Optionally filter by wallet_id to show only transactions involving a specific wallet.
    Transactions are ordered by creation date (newest first).

    Query params:
        page: Page number (1-indexed, default=1)
        page_size: Items per page (max=100, default=20)
    """
    try:
        # Validate pagination parameters
        if page < 1:
            return 400, {"detail": "Page must be >= 1"}
        if page_size < 1 or page_size > 100:
            return 400, {"detail": "Page size must be between 1 and 100"}

        offset = (page - 1) * page_size

        # Get paginated transactions
        if wallet_id:
            transactions = get_user_transactions_by_wallet(
                user=request.auth,
                wallet_id=wallet_id,
                limit=page_size,
                offset=offset
            )
            # Get total count for pagination metadata
            total_count = LedgerRepository.get_wallet_transactions(wallet_id, request.auth.id).count()
        else:
            transactions = get_user_transactions(
                user=request.auth,
                limit=page_size,
                offset=offset
            )
            total_count = LedgerRepository.get_user_transactions(request.auth.id).count()

        # Build response items with postings (prefetched)
        items = []
        for txn in transactions:
            postings_out = [
                TransactionPostingOut(
                    wallet_id=p.wallet.id,
                    wallet_name=p.wallet.name,
                    wallet_currency=p.wallet.currency,
                    amount=p.amount,
                    direction=p.direction,
                    currency=p.currency,
                )
                for p in txn.postings.all()  # prefetched via repository
            ]
            items.append(TransactionListItem(
                id=txn.id,
                type=txn.type,
                description=txn.description,
                created_at=txn.created_at,
                reversal_of=txn.reversal_of_id,
                postings=postings_out,
            ))

        # Build pagination metadata
        total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0
        response = PaginatedTransactionResponse(
            items=items,
            count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
        return 200, response
    except LedgerError as e:
        return 400, {"detail": str(e)}


@router.get("/{uuid:transaction_id}", response={200: TransactionOut, 404: ErrorOut}, auth=JWTAuth())
def get_transaction(request: HttpRequest, transaction_id: UUID):
    """
    Retrieve detailed transaction information including all ledger postings.
    """
    try:
        txn = get_transaction_details(user=request.auth, transaction_id=transaction_id)
    except LedgerError as e:
        return 404, {"detail": str(e)}

    # Build postings list with wallet details
    postings_out = []
    for posting in txn.postings.all():
        postings_out.append(TransactionPostingOut(
            wallet_id=posting.wallet.id,
            wallet_name=posting.wallet.name,
            wallet_currency=posting.wallet.currency,
            amount=posting.amount,
            direction=posting.direction,
            currency=posting.currency,
        ))

    return 200, TransactionOut(
        id=txn.id,
        type=txn.type,
        description=txn.description,
        created_at=txn.created_at,
        postings=postings_out,
        reversal_of=txn.reversal_of_id,
    )


class RefundRequest(BaseModel):
    amount: Decimal


class TransferRequest(BaseModel):
    from_wallet_id: UUID
    to_wallet_id: UUID
    amount: Decimal
    description: str


@router.post("/{uuid:transaction_id}/reverse", response={200: Dict[str, Any]}, auth=JWTAuth())
def reverse(request: HttpRequest, transaction_id: UUID):
    txn = reverse_transaction(user=request.auth, transaction_id=transaction_id)
    return 200, {"message": "Transaction reversed successfully", "transaction_id": str(txn.id)}


@router.post("/{uuid:transaction_id}/refund", response={200: Dict[str, Any]}, auth=JWTAuth())
def refund(request: HttpRequest, transaction_id: UUID, payload: RefundRequest):
    txn = refund_transaction(user=request.auth, transaction_id=transaction_id, refund_amount=payload.amount)
    return 200, {"message": "Transaction refunded successfully", "transaction_id": str(txn.id)}


@router.post("/transfer", response={200: Dict[str, Any], 400: Dict[str, Any]}, auth=JWTAuth())
def transfer(request: HttpRequest, payload: TransferRequest):
    """Transfer funds from one wallet to another.

    Assembles the 2-legged postings (DEBIT from_wallet, CREDIT to_wallet)
    and delegates all validation and persistence to create_transaction.
    """
    try:
        txn = create_transaction(
            user=request.auth,
            description=payload.description,
            postings=[
                {
                    "wallet_id": payload.from_wallet_id,
                    "amount": payload.amount,
                    "direction": LedgerPosting.Direction.DEBIT,
                },
                {
                    "wallet_id": payload.to_wallet_id,
                    "amount": payload.amount,
                    "direction": LedgerPosting.Direction.CREDIT,
                },
            ],
        )
        return 200, {"message": "Transfer completed successfully", "transaction_id": str(txn.id)}
    except InsufficientFundsError as e:
        return 400, {"detail": str(e)}
    except CurrencyMismatchError as e:
        return 400, {"detail": str(e)}
    except LedgerError as e:
        return 400, {"detail": str(e)}
