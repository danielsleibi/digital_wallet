from ninja import Router
from pydantic import BaseModel
from typing import Any, Dict
from uuid import UUID
from apps.ledger.services.compensation_service import reverse_transaction, refund_transaction
from django.http import HttpRequest
from apps.common.auth.bearer import JWTAuth
from decimal import Decimal

router = Router(tags=["Transactions"])

class RefundRequest(BaseModel):
    amount: Decimal

@router.post("/{transaction_id}/reverse", response={200: Dict[str, Any]}, auth=JWTAuth())
def reverse(request: HttpRequest, transaction_id: UUID):
    txn = reverse_transaction(user=request.user, transaction_id=transaction_id)
    return 200, {"message": "Transaction reversed successfully", "transaction_id": str(txn.id)}

@router.post("/{transaction_id}/refund", response={200: Dict[str, Any]}, auth=JWTAuth())
def refund(request: HttpRequest, transaction_id: UUID, payload: RefundRequest):
    txn = refund_transaction(user=request.user, transaction_id=transaction_id, refund_amount=payload.amount)
    return 200, {"message": "Transaction refunded successfully", "transaction_id": str(txn.id)}
