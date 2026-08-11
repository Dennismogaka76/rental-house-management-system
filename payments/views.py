from decimal import Decimal, InvalidOperation
import json

from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import ListView, TemplateView

from accounts.mixins import TenantRequiredMixin, AdminRequiredMixin
from tenancy.models import Tenancy

from .models import Payment
from . import mpesa
from .receipts import build_receipt_pdf


class PayView(TenantRequiredMixin, TemplateView):
    template_name = "payments/pay.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["tenancy"] = (
            Tenancy.objects.filter(tenant=self.request.user, active=True)
            .select_related("room", "room__apartment").first()
        )
        ctx["paybill"] = getattr(settings, "MPESA_PAYBILL", "")
        ctx["account_number"] = getattr(settings, "MPESA_ACCOUNT_NUMBER", "")
        ctx["business_name"] = getattr(settings, "MPESA_BUSINESS_NAME", "")
        return ctx

    def post(self, request):
        tenancy = Tenancy.objects.filter(tenant=request.user, active=True).first()
        if not tenancy:
            messages.error(request, "You have no active tenancy.")
            return redirect("payments:pay")
        phone = request.POST.get("phone") or request.user.phone_number
        try:
            amount = Decimal(request.POST.get("amount") or "0")
        except InvalidOperation:
            amount = Decimal("0")
        if amount <= 0:
            messages.error(request, "Enter a valid amount.")
            return redirect("payments:pay")
        payment = mpesa.initiate_stk_push(
            tenant=request.user, tenancy=tenancy, amount=amount, phone=phone,
        )
        if payment.status == Payment.Status.FAILED:
            messages.error(request, f"STK push failed: {payment.notes}")
        else:
            messages.success(request, "STK push sent. Enter your M-Pesa PIN on your phone.")
        return redirect("payments:history")


class ManualPaybillPaymentView(TenantRequiredMixin, View):
    """Tenant paid straight on the Paybill and submits the M-Pesa code."""

    def post(self, request):
        tenancy = Tenancy.objects.filter(tenant=request.user, active=True).first()
        if not tenancy:
            messages.error(request, "You have no active tenancy.")
            return redirect("payments:pay")
        code = (request.POST.get("mpesa_receipt") or "").strip()
        try:
            amount = Decimal(request.POST.get("amount") or "0")
        except InvalidOperation:
            amount = Decimal("0")
        if not code or amount <= 0:
            messages.error(request, "Enter the M-Pesa confirmation code and the amount paid.")
            return redirect("payments:pay")
        mpesa.record_manual_paybill_payment(
            tenant=request.user, tenancy=tenancy, amount=amount, mpesa_receipt=code,
        )
        messages.success(
            request,
            "Payment submitted. It will reflect on your balance once the admin verifies the code.",
        )
        return redirect("payments:history")


class VerifyManualPaymentView(AdminRequiredMixin, View):
    """Admin confirms a Paybill payment; balance updates immediately."""

    def post(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk)
        mpesa.verify_manual_payment(payment)
        messages.success(request, f"Payment {payment.reference_number} verified and balance updated.")
        return redirect("payments:admin_list")


class PaymentHistoryView(TenantRequiredMixin, ListView):
    template_name = "payments/history.html"
    context_object_name = "payments"
    paginate_by = 25

    def get_queryset(self):
        return Payment.objects.filter(tenant=self.request.user)


class DownloadReceiptView(TenantRequiredMixin, View):
    def get(self, request, pk):
        payment = get_object_or_404(
            Payment, pk=pk, tenant=request.user, status=Payment.Status.SUCCESS
        )
        pdf = build_receipt_pdf(payment)
        resp = HttpResponse(pdf, content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="receipt-{payment.reference_number}.pdf"'
        return resp


class AdminPaymentListView(AdminRequiredMixin, ListView):
    template_name = "payments/admin_list.html"
    context_object_name = "payments"
    paginate_by = 40

    def get_queryset(self):
        qs = Payment.objects.select_related("tenant", "tenancy", "tenancy__room")
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs


@method_decorator(csrf_exempt, name="dispatch")
class MpesaCallbackView(View):
    """Public endpoint hit by Safaricom. CSRF-exempt by necessity."""
    def post(self, request):
        try:
            body = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"ResultCode": 1, "ResultDesc": "Invalid JSON"}, status=400)
        mpesa.handle_callback(body)
        # Daraja expects an acknowledgement.
        return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})
