"""Custom user model: phone-number-based auth with tenant/admin roles."""
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


PHONE_VALIDATOR = RegexValidator(
    regex=r"^\+?\d{9,15}$",
    message="Phone number must be 9-15 digits, optionally starting with +.",
)


class UserManager(BaseUserManager):
    """Manager that keys users off phone_number instead of username."""

    use_in_migrations = True

    def _create_user(self, phone_number, password, **extra_fields):
        if not phone_number:
            raise ValueError("Phone number is required")
        phone_number = phone_number.strip()
        user = self.model(phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("role", User.Role.TENANT)
        return self._create_user(phone_number, password, **extra_fields)

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", User.Role.ADMIN)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        # createsuperuser requires these; provide safe defaults when absent.
        extra_fields.setdefault("full_name", "Administrator")
        extra_fields.setdefault("id_number", f"ADMIN-{timezone.now().timestamp():.0f}")
        return self._create_user(phone_number, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        TENANT = "tenant", "Tenant"
        ADMIN = "admin", "Admin"

    full_name = models.CharField(max_length=150)
    phone_number = models.CharField(
        max_length=20, unique=True, validators=[PHONE_VALIDATOR]
    )
    id_number = models.CharField(max_length=30, unique=True)
    id_photo = models.ImageField(upload_to="id_photos/", blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.TENANT)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS = ["full_name", "id_number"]

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ("-date_joined",)

    def __str__(self) -> str:
        return f"{self.full_name} ({self.phone_number})"

    def save(self, *args, **kwargs):
        # Capitalize each token of the full name regardless of user input casing.
        if self.full_name:
            self.full_name = " ".join(
                part.capitalize() for part in self.full_name.strip().split()
            )
        super().save(*args, **kwargs)

    @property
    def is_tenant(self) -> bool:
        return self.role == self.Role.TENANT

    @property
    def is_admin_user(self) -> bool:
        return self.role == self.Role.ADMIN or self.is_staff



class PasswordResetCode(models.Model):
    """Short-lived, hashed, single-use code for self-service password reset."""

    TTL_MINUTES = 10
    MAX_ATTEMPTS = 5

    class Channel(models.TextChoices):
        SMS = "sms", "SMS"
        EMAIL = "email", "Email"

    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="password_reset_codes"
    )
    code_hash = models.CharField(max_length=128)
    channel = models.CharField(max_length=10, choices=Channel.choices, default=Channel.SMS)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Reset code for {self.user.phone_number}"

    @classmethod
    def issue(cls, user, raw_code: str, channel: str = "sms") -> "PasswordResetCode":
        from django.contrib.auth.hashers import make_password
        from datetime import timedelta

        return cls.objects.create(
            user=user,
            code_hash=make_password(raw_code),
            channel=channel,
            expires_at=timezone.now() + timedelta(minutes=cls.TTL_MINUTES),
        )

    @property
    def is_expired(self) -> bool:
        return self.used_at is not None or timezone.now() > self.expires_at

    def matches(self, raw_code: str) -> bool:
        from django.contrib.auth.hashers import check_password

        return check_password(raw_code, self.code_hash)
