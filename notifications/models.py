from django.conf import settings
from django.db import models
from django.utils import timezone

from apartments.models import Apartment


class NotificationLog(models.Model):
    class Channel(models.TextChoices):
        SMS = "sms", "SMS"
        EMAIL = "email", "Email"

    class Status(models.TextChoices):
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="notifications_log",
    )
    channel = models.CharField(max_length=10, choices=Channel.choices)
    recipient = models.CharField(max_length=200)
    subject = models.CharField(max_length=200, blank=True)
    body = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SENT)
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.channel} -> {self.recipient} [{self.status}]"


class Notification(models.Model):
    """In-app notification shown in the bell dropdown."""

    class Category(models.TextChoices):
        ANNOUNCEMENT = "announcement", "Announcement"
        REQUEST = "request", "Room Request"
        PAYMENT = "payment", "Payment"
        REGISTRATION = "registration", "Registration"
        TENANCY = "tenancy", "Tenancy"
        SYSTEM = "system", "System"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="app_notifications"
    )
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.SYSTEM)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    url = models.CharField(max_length=300, blank=True, default="")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.title} -> {self.user_id}"


class AnnouncementAudience(models.TextChoices):
    ALL = "all", "All tenants"
    APARTMENT = "apartment", "Tenants of an apartment"
    TENANT = "tenant", "A specific tenant"


class Announcement(models.Model):
    """Admin memoranda / notices / announcements broadcast to tenants."""

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="sent_announcements",
    )
    audience = models.CharField(max_length=15, choices=AnnouncementAudience.choices)
    apartment = models.ForeignKey(
        Apartment, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="announcements",
    )
    tenant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="targeted_announcements",
    )
    title = models.CharField(max_length=200)
    body = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.title} [{self.audience}]"


class MessageThread(models.Model):
    """A 1:1 thread between a tenant and admins."""

    tenant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="message_threads"
    )
    subject = models.CharField(max_length=200, blank=True, default="Conversation")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)

    def __str__(self) -> str:
        return f"Thread with {self.tenant}"


class Message(models.Model):
    thread = models.ForeignKey(MessageThread, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="sent_messages",
    )
    body = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("created_at",)

    def __str__(self) -> str:
        return f"Msg from {self.sender_id} in {self.thread_id}"
