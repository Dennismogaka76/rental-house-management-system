from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        TIMEOUT = "timeout", "Timeout"

    class Method(models.TextChoices):
        MPESA = "mpesa", "M-Pesa"
        CASH = "cash", "Cash"
        BANK = "bank", "Bank Transfer"

    tenant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payments"
    )
    tenancy = models.ForeignKey(
        "tenancy.Tenancy", on_delete=models.SET_NULL, null=True, blank=True, related_name="payments"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reference_number = models.CharField(max_length=40, unique=True)
    payment_method = models.CharField(max_length=20, choices=Method.choices, default=Method.MPESA)
    mpesa_receipt = models.CharField(max_length=50, blank=True, default="")
    checkout_request_id = models.CharField(max_length=100, blank=True, default="", db_index=True)
    merchant_request_id = models.CharField(max_length=100, blank=True, default="")
    phone_number = models.CharField(max_length=20, blank=True, default="")
    transaction_date = models.DateTimeField(default=timezone.now)
    balance_before = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    balance_after = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ("-transaction_date",)
        indexes = [
            models.Index(fields=["tenant", "-transaction_date"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return f"{self.reference_number} - {self.tenant.full_name} - {self.amount}"
