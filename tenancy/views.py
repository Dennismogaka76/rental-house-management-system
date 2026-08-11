from django import forms
from django.contrib import messages
from django.db.models import Q, Sum, F
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.views.generic import CreateView, ListView, DetailView, View, TemplateView, FormView

from accounts.mixins import AdminRequiredMixin, TenantRequiredMixin
from accounts.security import SudoRequiredMixin
from apartments.models import Apartment

from .forms import RoomRequestForm, ReviewRequestForm
from .models import RoomRequest, Tenancy
from . import services


class TenantRequestCreateView(TenantRequiredMixin, CreateView):
    model = RoomRequest
    form_class = RoomRequestForm
    template_name = "tenancy/request_form.html"
    success_url = reverse_lazy("tenancy:my_requests")

    def dispatch(self, request, *args, **kwargs):
        # Enforce "change room" rule: existing tenancy allowed only when
        # balance is 0 or in credit (<= 0).
        active = Tenancy.objects.filter(tenant=request.user, active=True).first()
        if active and (active.balance or 0) > 0:
            messages.error(
                request,
                "You can only change rooms once your outstanding balance is fully cleared.",
            )
            return redirect("accounts:tenant_dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["is_change_room"] = Tenancy.objects.filter(
            tenant=self.request.user, active=True,
        ).exists()
        return ctx

    def form_valid(self, form):
        form.instance.tenant = self.request.user
        messages.success(self.request, "Room request submitted. Awaiting admin approval.")
        return super().form_valid(form)


class TenantRequestListView(TenantRequiredMixin, ListView):
    template_name = "tenancy/my_requests.html"
    context_object_name = "requests"
    paginate_by = 20

    def get_queryset(self):
        return RoomRequest.objects.filter(tenant=self.request.user).select_related("apartment", "room")


class AdminRequestListView(AdminRequiredMixin, ListView):
    template_name = "tenancy/admin_requests.html"
    context_object_name = "requests"
    paginate_by = 25

    def get_queryset(self):
        qs = RoomRequest.objects.select_related("tenant", "apartment", "room")
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs


class ApproveRequestView(SudoRequiredMixin, AdminRequiredMixin, View):
    def post(self, request, pk):
        req = get_object_or_404(RoomRequest, pk=pk)
        form = ReviewRequestForm(request.POST)
        note = form.cleaned_data["admin_note"] if form.is_valid() else ""
        try:
            services.approve_room_request(req, request.user, note)
            messages.success(request, f"Request approved. New tenancy created for {req.tenant.full_name}.")
        except ValueError as e:
            messages.error(request, str(e))
        return redirect("tenancy:admin_requests")


class RejectRequestView(SudoRequiredMixin, AdminRequiredMixin, View):
    def post(self, request, pk):
        req = get_object_or_404(RoomRequest, pk=pk)
        form = ReviewRequestForm(request.POST)
        note = form.cleaned_data["admin_note"] if form.is_valid() else ""
        try:
            services.reject_room_request(req, request.user, note)
            messages.info(request, "Request rejected.")
        except ValueError as e:
            messages.error(request, str(e))
        return redirect("tenancy:admin_requests")


class AdminTenancyListView(AdminRequiredMixin, ListView):
    template_name = "tenancy/admin_tenancies.html"
    context_object_name = "tenancies"
    paginate_by = 30

    def get_queryset(self):
        qs = (
            Tenancy.objects.filter(active=True)
            .select_related("tenant", "room", "room__apartment")
        )
        if self.request.GET.get("balance") == "1":
            qs = qs.filter(balance__gt=0)
        apt = self.request.GET.get("apartment")
        if apt:
            qs = qs.filter(room__apartment_id=apt)
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(
                Q(tenant__full_name__icontains=q)
                | Q(tenant__phone_number__icontains=q)
                | Q(tenant__id_number__icontains=q)
                | Q(room__room_number__icontains=q)
                | Q(room__apartment__name__icontains=q)
            )
        return qs.order_by(F("balance").desc())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["apartments"] = Apartment.objects.all()
        ctx["selected_apartment"] = self.request.GET.get("apartment", "")
        ctx["q"] = self.request.GET.get("q", "")
        ctx["balance_only"] = self.request.GET.get("balance") == "1"
        return ctx


class SendBalanceReminderView(AdminRequiredMixin, View):
    """Send an in-app + SMS reminder to a tenant with an outstanding balance."""

    def post(self, request, pk):
        tenancy = get_object_or_404(Tenancy, pk=pk, active=True)
        try:
            from notifications.services import send_balance_reminder
            send_balance_reminder(tenancy, sender=request.user)
            messages.success(
                request,
                f"Reminder sent to {tenancy.tenant.full_name}.",
            )
        except Exception as e:
            messages.error(request, f"Could not send reminder: {e}")
        return redirect(
            request.META.get("HTTP_REFERER")
            or reverse("tenancy:admin_tenancies") + "?balance=1"
        )


class VacateForm(forms.Form):
    vacate_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )
    confirm = forms.BooleanField(
        required=True,
        label="I confirm I will vacate on this date.",
    )

    def clean_vacate_date(self):
        d = self.cleaned_data["vacate_date"]
        if d < timezone.localdate():
            raise forms.ValidationError("Vacate date must be today or in the future.")
        return d


class VacateRoomView(TenantRequiredMixin, FormView):
    template_name = "tenancy/vacate_form.html"
    form_class = VacateForm
    success_url = reverse_lazy("accounts:tenant_dashboard")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        self.tenancy = Tenancy.objects.filter(
            tenant=self.request.user, active=True,
        ).select_related("room", "room__apartment").first()
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["tenancy"] = self.tenancy
        return ctx

    def form_valid(self, form):
        if not self.tenancy:
            messages.error(self.request, "You have no active tenancy to vacate.")
            return redirect("accounts:tenant_dashboard")
        d = form.cleaned_data["vacate_date"]
        self.tenancy.vacate_date = d
        self.tenancy.vacate_confirmed_at = timezone.now()
        self.tenancy.save(update_fields=["vacate_date", "vacate_confirmed_at", "updated_at"])
        try:
            from notifications.services import notify_vacate_declared
            notify_vacate_declared(self.tenancy, d)
        except Exception:
            pass
        messages.success(
            self.request,
            f"Vacate date {d} confirmed. Admin has been notified.",
        )
        return super().form_valid(form)
