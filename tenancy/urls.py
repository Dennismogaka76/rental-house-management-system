from django.urls import path
from . import views

app_name = "tenancy"

urlpatterns = [
    path("request/", views.TenantRequestCreateView.as_view(), name="request_create"),
    path("my-requests/", views.TenantRequestListView.as_view(), name="my_requests"),
    path("vacate/", views.VacateRoomView.as_view(), name="vacate"),
    path("admin/requests/", views.AdminRequestListView.as_view(), name="admin_requests"),
    path("admin/requests/<int:pk>/approve/", views.ApproveRequestView.as_view(), name="request_approve"),
    path("admin/requests/<int:pk>/reject/", views.RejectRequestView.as_view(), name="request_reject"),
    path("admin/tenancies/", views.AdminTenancyListView.as_view(), name="admin_tenancies"),
    path("admin/tenancies/<int:pk>/remind/", views.SendBalanceReminderView.as_view(), name="send_balance_reminder"),
]
