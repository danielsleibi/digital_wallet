from django.db import models
from django.conf import settings
from decimal import Decimal
from django.core.validators import MinValueValidator
from apps.wallets.models import Wallet
import uuid

class Transaction(models.Model):
    class TransactionType(models.TextChoices):
        NORMAL = "normal"
        REVERSAL = "reversal"
        REFUND = "refund"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(
        max_length=10,
        choices=TransactionType.choices,
        default=TransactionType.NORMAL
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="transactions"
    )
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    # For tracking reversals and refunds
    reversal_of = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reversals"
    )

    class Meta:
        indexes = [
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        return f"Transaction {self.id}"



class LedgerPosting(models.Model):
    class Direction(models.TextChoices):
        DEBIT = "debit"
        CREDIT = "credit"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.PROTECT,
        related_name="postings"
    )
    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.PROTECT,
        related_name="postings"
    )
    amount = models.DecimalField(
        max_digits=18,
        decimal_places=6
    )
    direction = models.CharField(
        max_length=6,
        choices=Direction.choices
    )
    currency = models.CharField(max_length=3)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["wallet", "created_at"]),
            models.Index(fields=["transaction"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(amount=Decimal("0")),
                name="posting_amount_non_zero"
            ),
        ]

    def __str__(self):
        return f"{self.direction} {self.amount} {self.currency}"