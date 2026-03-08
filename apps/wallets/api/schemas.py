# apps/wallets/api/schemas.py

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class WalletCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Human-readable wallet name")
    currency: str = Field(..., min_length=3, max_length=3, description="ISO-4217 currency code (e.g. USD)")


class WalletOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    currency: str
    status: str


class BalanceOut(BaseModel):
    wallet_id: UUID
    balance: Decimal


class ErrorOut(BaseModel):
    detail: str
