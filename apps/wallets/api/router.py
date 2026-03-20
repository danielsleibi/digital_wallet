# apps/wallets/api/router.py

from typing import List, Any, Dict
from uuid import UUID

from django.http import HttpRequest
from ninja import Router

from apps.common.auth.bearer import JWTAuth
from apps.common.exceptions import LedgerError, InsufficientFundsError, CurrencyMismatchError
from apps.wallets.api.schemas import WalletCreateIn, WalletOut, BalanceOut, ErrorOut, FundWalletIn, FundWalletOut
from apps.wallets.services.wallet_service import get_user_wallets, get_wallet_balance, create_wallet, fund_wallet as fund_wallet_service
from apps.wallets.repository import WalletRepository
from apps.ledger.services.transaction_service import create_transaction
from apps.ledger.models import LedgerPosting
from apps.ledger.repository import LedgerRepository
from decimal import Decimal

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


@router.post("/{wallet_id}/fund", response={200: FundWalletOut, 400: ErrorOut, 404: ErrorOut}, auth=JWTAuth())
def fund_wallet(request: HttpRequest, wallet_id: UUID, payload: FundWalletIn):
    """
    Add funds to a wallet from a specified system wallet.
    The system wallet is debited (allowing negative balance) and the target wallet is credited.
    Both wallets must be active and have the same currency.
    """
    try:
        txn, new_balance = fund_wallet_service(
            user=request.auth,
            wallet_id=wallet_id,
            amount=payload.amount,
            system_wallet_name=payload.system_wallet_name,
            description=payload.description or f"Funding for wallet"
        )
        return 200, {
            "message": "Wallet funded successfully",
            "transaction_id": str(txn.id),
            "wallet_id": str(wallet_id),
            "amount": payload.amount,
            "new_balance": new_balance
        }
    except ValueError as e:
        return 400, {"detail": str(e)}
    except LedgerError as e:
        return 400 if "not found or inactive" in str(e) else 404, {"detail": str(e)}

