from django import forms
from django.core.exceptions import ValidationError

from .models import Apartment, Room


class ApartmentForm(forms.ModelForm):
    class Meta:
        model = Apartment
        fields = ("name", "description", "location", "total_rooms")
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "location": forms.TextInput(attrs={"class": "form-control"}),
            "total_rooms": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
        }

    def clean_total_rooms(self):
        total = self.cleaned_data.get("total_rooms") or 0
        if self.instance and self.instance.pk:
            existing = self.instance.rooms.count()
            if total < existing:
                raise ValidationError(
                    f"Cannot set total to {total}: {existing} room(s) are already registered "
                    f"for this apartment."
                )
        return total


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ("apartment", "room_number", "floor", "room_type", "monthly_rent")
        widgets = {
            "apartment": forms.Select(attrs={"class": "form-select"}),
            "room_number": forms.TextInput(attrs={"class": "form-control"}),
            "floor": forms.TextInput(attrs={"class": "form-control"}),
            "room_type": forms.Select(attrs={"class": "form-select"}),
            "monthly_rent": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": 0}),
        }

    def clean(self):
        cleaned = super().clean()
        apartment = cleaned.get("apartment")
        if apartment is not None:
            # Count existing rooms, excluding this instance on edit.
            qs = apartment.rooms.all()
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            existing = qs.count()
            capacity = apartment.total_rooms or 0
            if existing + 1 > capacity:
                raise ValidationError(
                    f"Cannot add another room to “{apartment.name}”. "
                    f"It already has {existing} of {capacity} room(s) declared. "
                    f"Increase the apartment's total rooms first."
                )
        return cleaned
