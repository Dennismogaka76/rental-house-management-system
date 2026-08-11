from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.NotificationListView.as_view(), name="list"),
    path("mark-all-read/", views.MarkAllReadView.as_view(), name="mark_all_read"),
    path("<int:pk>/read/", views.MarkNotificationReadView.as_view(), name="mark_read"),

    path("messages/", views.InboxView.as_view(), name="inbox"),
    path("messages/new/", views.TenantNewMessageView.as_view(), name="tenant_new_message"),
    path("messages/<int:pk>/", views.ThreadDetailView.as_view(), name="thread"),

    path("admin/announce/", views.AnnouncementCreateView.as_view(), name="announcement_new"),
]
