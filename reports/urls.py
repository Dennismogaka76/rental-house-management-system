from django.urls import path
from . import views

app_name = "reports"

urlpatterns = [
    path("", views.ReportsIndexView.as_view(), name="index"),
    path("<str:kind>.<str:fmt>", views.ReportDownloadView.as_view(), name="download"),
]
