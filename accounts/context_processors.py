def user_flags(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"is_admin_user": False, "is_tenant_user": False, "pending_requests_count": 0}
    pending = 0
    if getattr(user, "is_admin_user", False):
        try:
            from tenancy.models import RoomRequest
            pending = RoomRequest.objects.filter(status=RoomRequest.Status.PENDING).count()
        except Exception:
            pending = 0
    return {
        "is_admin_user": getattr(user, "is_admin_user", False),
        "is_tenant_user": getattr(user, "is_tenant", False),
        "pending_requests_count": pending,
    }
