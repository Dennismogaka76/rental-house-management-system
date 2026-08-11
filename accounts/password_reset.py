"""Self-service password reset using a short-lived code sent by SMS or email."""
import re
import secrets

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import FormView

from .forms import validate_strong_password
from .models import PasswordResetCode, User

SESSION_KEY = "pwd_reset_user_id"
SESSION_VERIFIED = "pwd_reset_verified"
DIGITS_RE = re.compile(r"^\d{6}$")

NEUTRAL_MSG = (
    "If an account matches those details, a reset code has been sent. "
    "Enter it below."
)


def _find_user(identifier: str):
    ident = (identifier or "").strip()
    if not ident:
        return None
    if "@" in ident:
        return User.objects.filter(email__iexact=ident, is_active=True).first()
    phone = ident.replace(" ", "")
    if phone.startswith("0"):
        phone = "+254" + phone[1:]
    elif phone.startswith("254"):
        phone = "+" + phone
    return User.objects.filter(phone_number=phone, is_active=True).first()


def _mask_phone(phone: str) -> str:
    return f"{phone[:7]}***{phone[-2:]}" if phone and len(phone) > 9 else "your phone"


def _mask_email(email: str) -> str:
    if not email or "@" not in email:
        return "your email"
    name, domain = email.split("@", 1)
    return f"{name[:2]}***@{domain}"


class RequestCodeForm(forms.Form):
    identifier = forms.CharField(
        label="Phone number or email",
        widget=forms.TextInput(
            attrs={"class": "form-control", "autofocus": True,
                   "placeholder": "+254712345678 or you@example.com"}
        ),
    )
    channel = forms.ChoiceField(
        label="Send the code by",
        choices=(("sms", "SMS to my phone"), ("email", "Email")),
        initial="sms",
        widget=forms.RadioSelect,
    )


class VerifyCodeForm(forms.Form):
    code = forms.CharField(
        label="6-digit code",
        widget=forms.TextInput(
            attrs={"class": "form-control form-control-lg text-center",
                   "inputmode": "numeric", "maxlength": "6", "autofocus": True}
        ),
    )

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").strip()
        if not DIGITS_RE.match(code):
            raise ValidationError("Enter the 6-digit code exactly as received.")
        return code


class SetPasswordForm(forms.Form):
    new_password = forms.CharField(
        label="New password",
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "data-validate": "password", "autofocus": True}
        ),
    )
    confirm_password = forms.CharField(
        label="Confirm new password",
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "data-validate": "confirm"}
        ),
    )

    def clean_new_password(self):
        pwd = self.cleaned_data.get("new_password") or ""
        validate_strong_password(pwd)
        return pwd

    def clean(self):
        cleaned = super().clean()
        pwd = cleaned.get("new_password")
        confirm = cleaned.get("confirm_password")
        if pwd and confirm and pwd != confirm:
            raise ValidationError({"confirm_password": "Passwords do not match."})
        return cleaned


class PasswordResetRequestView(FormView):
    template_name = "accounts/password_reset_request.html"
    form_class = RequestCodeForm

    def form_valid(self, form):
        identifier = form.cleaned_data["identifier"]
        channel = form.cleaned_data["channel"]
        user = _find_user(identifier)

        if user:
            # Invalidate previous unused codes, then issue a fresh one.
            PasswordResetCode.objects.filter(user=user, used_at__isnull=True).update(
                used_at=timezone.now()
            )
            code = f"{secrets.randbelow(1000000):06d}"
            PasswordResetCode.issue(user, code, channel)
            body = (
                f"Your Apartment Rental password reset code is {code}. "
                "It expires in 10 minutes. If you did not request it, ignore this message."
            )
            try:
                from notifications.services import send_sms, send_email
                if channel == "email" and user.email:
                    send_email(user.email, "Password reset code", body, user=user)
                else:
                    send_sms(user.phone_number, body, user=user)
            except Exception:  # pragma: no cover - delivery is best-effort
                pass
            self.request.session[SESSION_KEY] = user.pk
            self.request.session[SESSION_VERIFIED] = False
            target = (
                _mask_email(user.email) if channel == "email" and user.email
                else _mask_phone(user.phone_number)
            )
            messages.info(self.request, f"A reset code was sent to {target}.")
        else:
            # Never reveal whether the account exists.
            self.request.session.pop(SESSION_KEY, None)
            messages.info(self.request, NEUTRAL_MSG)

        return redirect("accounts:password_reset_verify")


class PasswordResetVerifyView(FormView):
    template_name = "accounts/password_reset_verify.html"
    form_class = VerifyCodeForm

    def form_valid(self, form):
        user_id = self.request.session.get(SESSION_KEY)
        entry = None
        if user_id:
            entry = (
                PasswordResetCode.objects.filter(user_id=user_id, used_at__isnull=True)
                .order_by("-created_at")
                .first()
            )
        if not entry or entry.is_expired:
            messages.error(self.request, "That code has expired. Request a new one.")
            return redirect("accounts:password_reset")

        if not entry.matches(form.cleaned_data["code"]):
            entry.attempts += 1
            if entry.attempts >= PasswordResetCode.MAX_ATTEMPTS:
                entry.used_at = timezone.now()
                entry.save(update_fields=["attempts", "used_at"])
                messages.error(
                    self.request, "Too many incorrect attempts. Request a new code."
                )
                return redirect("accounts:password_reset")
            entry.save(update_fields=["attempts"])
            remaining = PasswordResetCode.MAX_ATTEMPTS - entry.attempts
            form.add_error("code", f"Incorrect code. {remaining} attempt(s) left.")
            return self.form_invalid(form)

        entry.used_at = timezone.now()
        entry.save(update_fields=["used_at"])
        self.request.session[SESSION_VERIFIED] = True
        return redirect("accounts:password_reset_set")


class PasswordResetSetView(FormView):
    template_name = "accounts/password_reset_set.html"
    form_class = SetPasswordForm

    def dispatch(self, request, *args, **kwargs):
        if not (request.session.get(SESSION_KEY) and request.session.get(SESSION_VERIFIED)):
            messages.error(request, "Verify your reset code first.")
            return redirect("accounts:password_reset")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = User.objects.filter(pk=self.request.session.get(SESSION_KEY)).first()
        if not user:
            messages.error(self.request, "Reset session expired. Start again.")
            return redirect("accounts:password_reset")
        user.set_password(form.cleaned_data["new_password"])
        user.save()
        self.request.session.pop(SESSION_KEY, None)
        self.request.session.pop(SESSION_VERIFIED, None)
        try:
            from notifications.services import send_sms
            send_sms(
                user.phone_number,
                "Your Apartment Rental password was changed. If this wasn't you, contact support.",
                user=user,
            )
        except Exception:  # pragma: no cover
            pass
        messages.success(self.request, "Password updated. You can now sign in.")
        return redirect("accounts:login")
