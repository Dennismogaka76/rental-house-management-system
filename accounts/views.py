from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView, View, TemplateView

from tenancy.models import Tenancy
from payments.models import Payment

from .forms import PhoneLoginForm, ProfileUpdateForm, RegistrationForm
from .mixins import AdminRequiredMixin
from .models import User


class RegisterView(CreateView):
    form_class = RegistrationForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("accounts:login")

    def form_valid(self, form):
        response = super().form_valid(form)
        # Fire welcome SMS/email (best-effort; failures logged, not blocking).
        try:
            from notifications.services import notify_registration
            notify_registration(self.object)
        except Exception:  # pragma: no cover
            pass
        messages.success(self.request, "Registration successful. Please log in.")
        return response


class PhoneLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = PhoneLoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy("accounts:dashboard")


class LogoutView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        logout(request)
        messages.info(request, "You have been signed out.")
        return redirect("accounts:login")

    post = get


class DashboardView(LoginRequiredMixin, TemplateView):
    """Routes users to the appropriate dashboard based on role."""

    def get(self, request, *args, **kwargs):
        if request.user.is_admin_user:
            return redirect("accounts:admin_dashboard")
        return redirect("accounts:tenant_dashboard")


class TenantDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/tenant_dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        tenancy = (
            Tenancy.objects.filter(tenant=user, active=True)
            .select_related("room", "room__apartment")
            .first()
        )
        ctx["tenancy"] = tenancy
        ctx["payments"] = Payment.objects.filter(tenant=user).order_by("-transaction_date")[:50]
        return ctx


class ProfileView(LoginRequiredMixin, UpdateView):
    form_class = ProfileUpdateForm
    template_name = "accounts/profile.html"
    success_url = reverse_lazy("accounts:profile")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Profile updated successfully.")
        return super().form_valid(form)


class AdminDashboardView(AdminRequiredMixin, TemplateView):
    template_name = "accounts/admin_dashboard.html"

    def get_context_data(self, **kwargs):
        from django.db.models import Count, Sum, Q
        from apartments.models import Apartment, Room
        from tenancy.models import RoomRequest
        from decimal import Decimal
        from django.utils import timezone

        ctx = super().get_context_data(**kwargs)
        now = timezone.now()

        rooms = Room.objects.all()
        active_tenancies = Tenancy.objects.filter(active=True)

        occupied = active_tenancies.count()
        total_rooms = rooms.count()

        ctx["stats"] = {
            "total_apartments": Apartment.objects.count(),
            "total_rooms": total_rooms,
            "occupied_rooms": occupied,
            "vacant_rooms": max(total_rooms - occupied, 0),
            "total_tenants": User.objects.filter(role=User.Role.TENANT).count(),
            "pending_requests": RoomRequest.objects.filter(status=RoomRequest.Status.PENDING).count(),
            "monthly_income": Payment.objects.filter(
                status=Payment.Status.SUCCESS,
                transaction_date__year=now.year,
                transaction_date__month=now.month,
            ).aggregate(total=Sum("amount"))["total"] or Decimal("0"),
            "outstanding_balances": active_tenancies.filter(balance__gt=0).aggregate(
                total=Sum("balance")
            )["total"] or Decimal("0"),
            "late_payments": active_tenancies.filter(balance__gt=0, penalty__gt=0).count(),
        }
        overpaid_qs = active_tenancies.filter(balance__lt=0).select_related("tenant", "room__apartment")
        ctx["overpaid_tenants"] = list(overpaid_qs[:10])
        ctx["overpaid_amount"] = sum((-t.balance for t in overpaid_qs), Decimal("0"))
        ctx["recent_payments"] = Payment.objects.select_related("tenant").order_by("-transaction_date")[:10]
        ctx["recent_requests"] = RoomRequest.objects.select_related("tenant", "room", "apartment").order_by("-created_at")[:10]
        return ctx
