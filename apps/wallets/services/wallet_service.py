# apps/wallets/services/wallet_service.py

import re
from uuid import UUID
from decimal import Decimal

from apps.wallets.models import Wallet
from apps.wallets.repository import WalletRepository
from apps.ledger.repository import LedgerRepository
from apps.ledger.services.transaction_service import create_transaction
from apps.ledger.models import LedgerPosting
from apps.common.exceptions import LedgerError, InsufficientFundsError, CurrencyMismatchError

# ISO-4217 codes are exactly 3 uppercase ASCII letters
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


def get_user_wallets(user):
    """
    Return all active wallets belonging to the authenticated user.
    """
    return WalletRepository.get_user_wallets(user.id)


def get_wallet_balance(user, wallet_id: UUID):
    """
    Return the current balance for a single wallet.
    Raises LedgerError if the wallet does not exist, is inactive, or
    does not belong to the requesting user.
    """

    try:
        wallet = WalletRepository.get_user_wallet(wallet_id, user.id)
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

    # Guard against duplicate (user, name, currency)
    if WalletRepository.wallet_exists(user_id=user.id, name=name, currency=currency):
        raise ValueError(
            f"A wallet named '{name}' with currency {currency} already exists for this account."
        )

    return WalletRepository.create_wallet(user=user, name=name, currency=currency)


def fund_wallet(user, wallet_id: UUID, amount: Decimal, system_wallet_name: str, description: str = "Wallet funding"):
    """
    Add funds to a user's wallet by debiting a system wallet.

    Args:
        user: The authenticated user (DomainUser or Django User)
        wallet_id: UUID of the target wallet to fund
        amount: Amount to credit to the target wallet (must be positive)
        system_wallet_name: Name of the system wallet to debit (e.g., "EQUITY" or "INCOME")
        description: Transaction description

    Returns:
        tuple: (Transaction, new_balance)

    Raises:
        ValueError: If amount is not positive or other validation fails
        LedgerError: If wallet not found, system wallet not found, or other ledger errors
    """
    # Validate amount
    if amount <= 0:
        raise ValueError("Amount must be positive")

    # Fetch target wallet (must belong to user and be active)
    try:
        target_wallet = WalletRepository.get_user_wallet(wallet_id, user.id)
    except Wallet.DoesNotExist:
        raise LedgerError("Wallet not found or access denied")

    # Prevent funding system wallets
    if target_wallet.is_system:
        raise ValueError("Cannot fund a system wallet")

    # Find the specified system wallet with matching currency
    system_wallet = WalletRepository.get_system_wallet(
        currency=target_wallet.currency,
        name=system_wallet_name
    )
    if not system_wallet:
        raise LedgerError(
            f"System wallet '{system_wallet_name}' not found or inactive for currency {target_wallet.currency}"
        )

    # Create the transaction
    txn = create_transaction(
        user=user,
        description=description or f"Funding for wallet {target_wallet.name}",
        postings=[
            {
                "wallet_id": system_wallet.id,
                "amount": amount,
                "direction": LedgerPosting.Direction.DEBIT,
            },
            {
                "wallet_id": target_wallet.id,
                "amount": amount,
                "direction": LedgerPosting.Direction.CREDIT,
            }
        ]
    )

    # Get new balance
    new_balance = LedgerRepository.get_wallet_balance(target_wallet)

    return txn, new_balance

