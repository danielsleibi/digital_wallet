# apps/ledger/api/schemas.py

"""
Pydantic schemas for ledger API request/response validation.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from apps.ledger.models import Transaction, LedgerPosting


class ErrorOut(BaseModel):
    """Error response schema."""
    detail: str


class TransactionPostingOut(BaseModel):
    """
    Schema for a single ledger posting in transaction responses.
    Shows wallet details and the posting amount/direction.
    """
    model_config = ConfigDict(from_attributes=True)

    wallet_id: UUID = Field(..., description="UUID of the wallet")
    wallet_name: str = Field(..., description="Name of the wallet")
    wallet_currency: str = Field(..., description="Currency code of the wallet")
    amount: Decimal = Field(..., description="Signed amount (negative=debit, positive=credit)")
    direction: str = Field(..., description="Posting direction: 'debit' or 'credit'")
    currency: str = Field(..., description="Currency of the posting (matches wallet currency)")


class TransactionOut(BaseModel):
    """
    Detailed transaction response including all postings.
    Used for GET /transactions/{transaction_id} endpoint.
    """
    model_config = ConfigDict(from_attributes=False)

    id: UUID = Field(..., description="Transaction UUID")
    type: str = Field(..., description="Transaction type: normal, reversal, or refund")
    description: str = Field(..., description="Transaction description")
    created_at: datetime = Field(..., description="Transaction creation timestamp")
    postings: list[TransactionPostingOut] = Field(..., description="List of ledger postings")
    reversal_of: UUID | None = Field(None, description="If this is a reversal/refund, the original transaction UUID")


class TransactionListItem(BaseModel):
    """
    Transaction representation for list views.
    Includes posting details to show wallet amounts.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Transaction UUID")
    type: str = Field(..., description="Transaction type: normal, reversal, or refund")
    description: str = Field(..., description="Transaction description")
    created_at: datetime = Field(..., description="Transaction creation timestamp")
    reversal_of: UUID | None = Field(None, description="Original transaction UUID if this is a reversal/refund")
    postings: list[TransactionPostingOut] = Field(..., description="Ledger postings for this transaction")


class PaginatedTransactionResponse(BaseModel):
    """Paginated response for transaction list endpoint."""
    model_config = ConfigDict(from_attributes=False)

    items: list[TransactionListItem] = Field(..., description="List of transactions for the current page")
    count: int = Field(..., description="Total number of transactions matching the query")
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Number of items per page")
    total_pages: int = Field(..., description="Total number of pages")
