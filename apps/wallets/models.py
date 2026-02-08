from django.db import models
from django.conf import settings

class Wallet(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active"
        ARCHIVED = "archived"

    id = models.UUIDField(primary_key=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="wallets"
    )
    name = models.CharField(max_length=100)
    currency = models.CharField(max_length=3)  # ISO-4217
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "name", "currency")
        indexes = [
            models.Index(fields=["user", "currency"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.currency})"