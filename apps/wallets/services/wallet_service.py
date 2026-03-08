# apps/wallets/services/wallet_service.py

import re
from uuid import UUID

from django.contrib.auth import get_user_model

from apps.wallets.models import Wallet
from apps.wallets.repository import WalletRepository
from apps.ledger.repository import LedgerRepository
from apps.common.exceptions import LedgerError

# ISO-4217 codes are exactly 3 uppercase ASCII letters
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")

User = get_user_model()


def get_user_wallets(user):
    """
    Return all active wallets belonging to the authenticated user.
    """
    return Wallet.objects.filter(user=user, status=Wallet.Status.ACTIVE).order_by("created_at")


def get_wallet_balance(user, wallet_id: UUID):
    """
    Return the current balance for a single wallet.
    Raises LedgerError if the wallet does not exist, is inactive, or
    does not belong to the requesting user.
    """
    try:
        wallet = Wallet.objects.get(id=wallet_id, user=user, status=Wallet.Status.ACTIVE)
    except Wallet.DoesNotExist:
        raise LedgerError("Wallet not found or access denied")

    return LedgerRepository.get_wallet_balance(wallet)


def create_wallet(user, name: str, currency: str) -> Wallet:
    """
    Create and return a new active wallet for the given user.

    Args:
        user: Django User model instance or DomainUser (resolved via id).
        name: Human-readable wallet name (1–100 characters).
        currency: ISO-4217 currency code (exactly 3 uppercase letters).

    Raises:
        ValueError: If the currency code is invalid or the (user, name, currency)
                    combination already exists.
    """
    # Normalise and validate currency
    currency = currency.strip().upper()
    if not _CURRENCY_RE.match(currency):
        raise ValueError(
            f"Invalid currency code '{currency}'. Must be exactly 3 uppercase letters (ISO-4217)."
        )

    # Resolve to a Django model instance when we receive a DomainUser dataclass
    if isinstance(user, str):
        user = User.objects.get(id=user)
    elif not hasattr(user, "pk"):
        # DomainUser dataclass – fetch the real Django model instance by id
        user = User.objects.get(id=user.id)

    # Guard against duplicate (user, name, currency)
    if WalletRepository.wallet_exists(user=user, name=name, currency=currency):
        raise ValueError(
            f"A wallet named '{name}' with currency {currency} already exists for this account."
        )

    return WalletRepository.create_wallet(user=user, name=name, currency=currency)

