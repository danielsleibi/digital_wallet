from ninja import Router
from pydantic import BaseModel
from typing import Any, Dict
from uuid import UUID
from apps.ledger.services.compensation_service import reverse_transaction, refund_transaction
from apps.ledger.services.transaction_service import create_transaction
from apps.ledger.models import LedgerPosting
from apps.common.exceptions import LedgerError, InsufficientFundsError, CurrencyMismatchError
from django.http import HttpRequest
from apps.common.auth.bearer import JWTAuth
from decimal import Decimal

router = Router(tags=["Transactions"])


class RefundRequest(BaseModel):
    amount: Decimal


class TransferRequest(BaseModel):
    from_wallet_id: UUID
    to_wallet_id: UUID
    amount: Decimal
    description: str


@router.post("/{transaction_id}/reverse", response={200: Dict[str, Any]}, auth=JWTAuth())
def reverse(request: HttpRequest, transaction_id: UUID):
    txn = reverse_transaction(user=request.auth, transaction_id=transaction_id)
    return 200, {"message": "Transaction reversed successfully", "transaction_id": str(txn.id)}


@router.post("/{transaction_id}/refund", response={200: Dict[str, Any]}, auth=JWTAuth())
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
