from django import forms
from .models import RoomRequest
from apartments.models import Room


class RoomRequestForm(forms.ModelForm):
    class Meta:
        model = RoomRequest
        fields = ("apartment", "room", "note")
        widgets = {
            "apartment": forms.Select(attrs={"class": "form-select", "id": "id_apartment"}),
            "room": forms.Select(attrs={"class": "form-select", "id": "id_room"}),
            "note": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Default queryset: only vacant rooms. The JS narrows this further
        # per selected apartment. Server-side we still validate.
        self.fields["room"].queryset = Room.objects.filter(tenant__isnull=True)

    def clean(self):
        cleaned = super().clean()
        apartment = cleaned.get("apartment")
        room = cleaned.get("room")
        if apartment and room and room.apartment_id != apartment.id:
            raise forms.ValidationError("Selected room does not belong to the chosen apartment.")
        if room and not room.is_vacant:
            raise forms.ValidationError("Selected room is not vacant anymore.")
        return cleaned


class ReviewRequestForm(forms.Form):
    admin_note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )
