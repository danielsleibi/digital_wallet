# apps/wallets/api/router.py

from typing import List, Any, Dict
from uuid import UUID

from django.http import HttpRequest
from ninja import Router

from apps.common.auth.bearer import JWTAuth
from apps.common.exceptions import LedgerError
from apps.wallets.api.schemas import WalletCreateIn, WalletOut, BalanceOut, ErrorOut
from apps.wallets.services.wallet_service import get_user_wallets, get_wallet_balance, create_wallet

router = Router(tags=["Wallets"])


@router.get("/", response={200: List[WalletOut]}, auth=JWTAuth())
def list_wallets(request: HttpRequest):
    """Return all active wallets belonging to the authenticated user."""
    wallets = get_user_wallets(user=request.auth.id)
    return 200, list(wallets)


@router.post("/", response={201: WalletOut, 400: ErrorOut}, auth=JWTAuth())
def create_wallet_endpoint(request: HttpRequest, payload: WalletCreateIn):
    """Create a new wallet for the authenticated user."""
    try:
        wallet = create_wallet(
            user=request.auth,
            name=payload.name,
            currency=payload.currency,
        )
        return 201, wallet
    except ValueError as e:
        return 400, {"detail": str(e)}


@router.get("/{wallet_id}/balance", response={200: BalanceOut, 404: Dict[str, Any]}, auth=JWTAuth())
def wallet_balance(request: HttpRequest, wallet_id: UUID):
    """Return the current ledger balance for a single wallet owned by the authenticated user."""
    try:
        balance = get_wallet_balance(user=request.auth.id, wallet_id=wallet_id)
        return 200, {"wallet_id": wallet_id, "balance": balance}
    except LedgerError as e:
        return 404, {"detail": str(e)}

