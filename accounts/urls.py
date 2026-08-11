from django.urls import path

from . import views
from .security import SudoConfirmView
from .password_reset import (
    PasswordResetRequestView,
    PasswordResetVerifyView,
    PasswordResetSetView,
)

app_name = "accounts"

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", views.PhoneLoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("tenant/dashboard/", views.TenantDashboardView.as_view(), name="tenant_dashboard"),
    path("admin/dashboard/", views.AdminDashboardView.as_view(), name="admin_dashboard"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("password-reset/", PasswordResetRequestView.as_view(), name="password_reset"),
    path("password-reset/verify/", PasswordResetVerifyView.as_view(), name="password_reset_verify"),
    path("password-reset/set/", PasswordResetSetView.as_view(), name="password_reset_set"),
    path("admin/confirm-password/", SudoConfirmView.as_view(), name="sudo_confirm"),
]
