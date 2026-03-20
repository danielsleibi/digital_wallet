# apps/wallets/api/schemas.py

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class WalletCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Human-readable wallet name")
    currency: str = Field(..., min_length=3, max_length=3, description="ISO-4217 currency code (e.g. USD)")


class FundWalletIn(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Amount to fund the wallet (must be positive)")
    description: str = Field("Wallet funding", max_length=255, description="Transaction description")
    system_wallet_name: str = Field(
        ...,
        description="Name of the system wallet to use (e.g., EQUITY or INCOME)",
        examples=["EQUITY", "INCOME"]
    )


class WalletOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    currency: str
    status: str


class BalanceOut(BaseModel):
    wallet_id: UUID
    balance: Decimal


class FundWalletOut(BaseModel):
    message: str
    transaction_id: UUID
    wallet_id: UUID
    amount: Decimal
    new_balance: Decimal


class ErrorOut(BaseModel):
    detail: str
