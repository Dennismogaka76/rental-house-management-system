import re

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from .models import User


SPECIAL_CHAR_RE = re.compile(r"[^A-Za-z0-9]")
LETTER_RE = re.compile(r"[A-Za-z]")
DIGIT_RE = re.compile(r"\d")
PHONE_KE_RE = re.compile(r"^\+254\d{9}$")


def validate_strong_password(password: str) -> None:
    """Server-side mirror of the client-side password checklist."""
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters long.")
    if not LETTER_RE.search(password):
        raise ValidationError("Password must contain at least 1 letter.")
    if not DIGIT_RE.search(password):
        raise ValidationError("Password must contain at least 1 number.")
    if not SPECIAL_CHAR_RE.search(password):
        raise ValidationError(
            "Password must contain at least 1 special character (e.g. , : .)."
        )


class RegistrationForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "data-validate": "password"}
        ),
        min_length=8,
        label="Password",
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "data-validate": "confirm"}
        ),
        min_length=8,
        label="Confirm Password",
    )

    class Meta:
        model = User
        fields = (
            "full_name",
            "phone_number",
            "id_number",
            "id_photo",
            "email",
        )
        widgets = {
            "full_name": forms.TextInput(attrs={"class": "form-control"}),
            "phone_number": forms.TextInput(
                attrs={"class": "form-control", "data-validate": "phone-ke"}
            ),
            "id_number": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(
                attrs={"class": "form-control", "data-validate": "email"}
            ),
            "id_photo": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }

    def clean_password(self):
        pwd = self.cleaned_data.get("password") or ""
        validate_strong_password(pwd)
        return pwd

    def clean(self):
        cleaned = super().clean()
        pwd = cleaned.get("password")
        confirm = cleaned.get("confirm_password")
        if pwd and confirm and pwd != confirm:
            raise ValidationError({"confirm_password": "Passwords do not match."})
        return cleaned

    def clean_phone_number(self):
        phone = (self.cleaned_data["phone_number"] or "").strip().replace(" ", "")
        if not PHONE_KE_RE.match(phone):
            raise ValidationError(
                "Phone number must be in the format +254XXXXXXXXX (9 digits after +254)."
            )
        if User.objects.filter(phone_number=phone).exists():
            raise ValidationError("A user with this phone number already exists.")
        return phone

    def clean_id_number(self):
        id_number = (self.cleaned_data["id_number"] or "").strip()
        if User.objects.filter(id_number=id_number).exists():
            raise ValidationError("A user with this ID number already exists.")
        return id_number

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip()
        # EmailField already validates format; normalise casing on the domain.
        return email.lower() if email else email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.role = User.Role.TENANT
        if commit:
            user.save()
        return user


class PhoneLoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Phone Number",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "autofocus": True,
                "data-validate": "phone-ke",
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("full_name", "email", "id_photo")
        widgets = {
            "full_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(
                attrs={"class": "form-control", "data-validate": "email"}
            ),
            "id_photo": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip()
        return email.lower() if email else email
