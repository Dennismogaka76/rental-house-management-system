from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apartments.models import Apartment, Room


class Tenancy(models.Model):
    """A tenant's active/inactive occupancy record for a room."""

    tenant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tenancies"
    )
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="tenancies")
    move_in_date = models.DateField(default=timezone.localdate)
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    penalty = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    next_due_date = models.DateField(null=True, blank=True)
    last_payment_date = models.DateTimeField(null=True, blank=True)
    deposit = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    active = models.BooleanField(default=True)
    penalty_applied_month = models.CharField(max_length=7, blank=True, default="")
    vacate_date = models.DateField(null=True, blank=True,
                                   help_text="Date the tenant has declared they'll vacate.")
    vacate_confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-active", "-created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("tenant",),
                condition=models.Q(active=True),
                name="unique_active_tenancy_per_tenant",
            )
        ]

    def __str__(self) -> str:
        return f"{self.tenant.full_name} @ {self.room}"

    @property
    def total_due(self) -> Decimal:
        return (self.balance or Decimal("0")) + (self.penalty or Decimal("0"))

    @property
    def has_overpayment(self) -> bool:
        return (self.balance or Decimal("0")) < 0

    @property
    def overpayment(self) -> Decimal:
        b = self.balance or Decimal("0")
        return -b if b < 0 else Decimal("0")


class RoomRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    tenant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="room_requests"
    )
    apartment = models.ForeignKey(Apartment, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    note = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_requests",
    )

    class Meta:
        # Pending first, then approved, then rejected; newest inside each group.
        ordering = (
            models.Case(
                models.When(status="pending", then=0),
                models.When(status="approved", then=1),
                models.When(status="rejected", then=2),
                output_field=models.IntegerField(),
            ),
            "-created_at",
        )

    def __str__(self) -> str:
        return f"{self.tenant.full_name} -> {self.room} [{self.status}]"
