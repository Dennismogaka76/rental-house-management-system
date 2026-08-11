from django.urls import path
from . import views

app_name = "payments"

urlpatterns = [
    path("pay/", views.PayView.as_view(), name="pay"),
    path("pay/manual/", views.ManualPaybillPaymentView.as_view(), name="manual_pay"),
    path("admin/verify/<int:pk>/", views.VerifyManualPaymentView.as_view(), name="verify_manual"),
    path("history/", views.PaymentHistoryView.as_view(), name="history"),
    path("receipt/<int:pk>/", views.DownloadReceiptView.as_view(), name="receipt"),
    path("admin/list/", views.AdminPaymentListView.as_view(), name="admin_list"),
    path("mpesa/callback/", views.MpesaCallbackView.as_view(), name="mpesa_callback"),
]
