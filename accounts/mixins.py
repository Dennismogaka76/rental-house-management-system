from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict access to staff / admin-role users."""

    raise_exception = False

    def test_func(self) -> bool:
        u = self.request.user
        return bool(u.is_authenticated and getattr(u, "is_admin_user", False))

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied("Admin access required.")
        return super().handle_no_permission()


class TenantRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    raise_exception = False

    def test_func(self) -> bool:
        u = self.request.user
        return bool(u.is_authenticated and getattr(u, "is_tenant", False))

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied("Tenants only.")
        return super().handle_no_permission()
