from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from accounts.mixins import AdminRequiredMixin
from accounts.security import SudoRequiredMixin

from .forms import ApartmentForm, RoomForm
from .models import Apartment, Room


class ApartmentListView(AdminRequiredMixin, ListView):
    model = Apartment
    template_name = "apartments/apartment_list.html"
    context_object_name = "apartments"
    paginate_by = 20


class ApartmentCreateView(SudoRequiredMixin, AdminRequiredMixin, CreateView):
    model = Apartment
    form_class = ApartmentForm
    template_name = "apartments/apartment_form.html"
    success_url = reverse_lazy("apartments:apartment_list")

    def form_valid(self, form):
        messages.success(self.request, "Apartment created.")
        return super().form_valid(form)


class ApartmentUpdateView(SudoRequiredMixin, AdminRequiredMixin, UpdateView):
    model = Apartment
    form_class = ApartmentForm
    template_name = "apartments/apartment_form.html"
    success_url = reverse_lazy("apartments:apartment_list")

    def form_valid(self, form):
        messages.success(self.request, "Apartment updated.")
        return super().form_valid(form)


class ApartmentDeleteView(SudoRequiredMixin, AdminRequiredMixin, DeleteView):
    model = Apartment
    template_name = "apartments/apartment_confirm_delete.html"
    success_url = reverse_lazy("apartments:apartment_list")

    def form_valid(self, form):
        messages.success(self.request, "Apartment deleted.")
        return super().form_valid(form)


class RoomListView(AdminRequiredMixin, ListView):
    model = Room
    template_name = "apartments/room_list.html"
    context_object_name = "rooms"
    paginate_by = 25

    def get_queryset(self):
        qs = Room.objects.select_related("apartment", "tenant")
        apt = self.request.GET.get("apartment")
        if apt:
            qs = qs.filter(apartment_id=apt)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["apartments"] = Apartment.objects.all()
        return ctx


class RoomCreateView(SudoRequiredMixin, AdminRequiredMixin, CreateView):
    model = Room
    form_class = RoomForm
    template_name = "apartments/room_form.html"
    success_url = reverse_lazy("apartments:room_list")

    def _capacity_full_apartment(self):
        for apt in Apartment.objects.all():
            if apt.total_rooms and apt.rooms.count() >= apt.total_rooms:
                # Return the first full apartment only if ALL apartments are full.
                pass
        # Detect an apartment that still has room.
        for apt in Apartment.objects.all():
            if not apt.total_rooms or apt.rooms.count() < apt.total_rooms:
                return None
        return Apartment.objects.first()

    def dispatch(self, request, *args, **kwargs):
        full = self._capacity_full_apartment()
        if full is not None:
            messages.error(
                request,
                f"No more rooms can be added! All {full.total_rooms} rooms "
                f"have been added for every apartment.",
            )
            return redirect("apartments:room_list")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Room created.")
        return super().form_valid(form)


class RoomUpdateView(SudoRequiredMixin, AdminRequiredMixin, UpdateView):
    model = Room
    form_class = RoomForm
    template_name = "apartments/room_form.html"
    success_url = reverse_lazy("apartments:room_list")

    def form_valid(self, form):
        messages.success(self.request, "Room updated.")
        return super().form_valid(form)


class RoomDeleteView(SudoRequiredMixin, AdminRequiredMixin, DeleteView):
    model = Room
    template_name = "apartments/room_confirm_delete.html"
    success_url = reverse_lazy("apartments:room_list")

    def form_valid(self, form):
        messages.success(self.request, "Room deleted.")
        return super().form_valid(form)


def vacant_rooms_json(request, apartment_id: int):
    """AJAX endpoint: return vacant rooms for a given apartment."""
    apartment = get_object_or_404(Apartment, pk=apartment_id)
    rooms = apartment.rooms.filter(tenant__isnull=True).values(
        "id", "room_number", "monthly_rent", "room_type", "floor"
    )
    return JsonResponse({"rooms": list(rooms)})
