from django.conf import settings
from django.db import models
from django.utils import timezone


class Apartment(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=200)
    total_rooms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name

    @property
    def occupied_count(self) -> int:
        return self.rooms.filter(tenant__isnull=False).count()

    @property
    def vacant_count(self) -> int:
        return self.rooms.filter(tenant__isnull=True).count()


class Room(models.Model):
    class RoomType(models.TextChoices):
        BEDSITTER = "bedsitter", "Bedsitter"
        SINGLE = "single", "Single Room"
        ONE_BR = "1br", "1 Bedroom"
        TWO_BR = "2br", "2 Bedroom"
        THREE_BR = "3br", "3 Bedroom"

    apartment = models.ForeignKey(Apartment, on_delete=models.CASCADE, related_name="rooms")
    room_number = models.CharField(max_length=20)
    floor = models.CharField(max_length=20, blank=True)
    room_type = models.CharField(max_length=20, choices=RoomType.choices, default=RoomType.SINGLE)
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2)
    tenant = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="occupied_room",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("apartment__name", "room_number")
        unique_together = (("apartment", "room_number"),)

    def __str__(self) -> str:
        return f"{self.apartment.name} - {self.room_number}"

    @property
    def is_vacant(self) -> bool:
        return self.tenant_id is None

    @property
    def occupancy_label(self) -> str:
        return self.tenant.full_name if self.tenant_id else "vacant"
