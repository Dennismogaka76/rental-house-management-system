"""Safaricom Daraja M-Pesa STK Push client + callback processing."""
from __future__ import annotations

import base64
import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from tenancy.models import Tenancy

from .models import Payment

logger = logging.getLogger(__name__)


BASE_URLS = {
    "sandbox": "https://sandbox.safaricom.co.ke",
    "production": "https://api.safaricom.co.ke",
}


def _base_url() -> str:
    return BASE_URLS.get(settings.MPESA_ENV, BASE_URLS["sandbox"])


def _normalize_msisdn(phone: str) -> str:
    """Convert 07XXXXXXXX / +2547XXXXXXXX to 2547XXXXXXXX."""
    phone = (phone or "").strip().replace(" ", "")
    if phone.startswith("+"):
        phone = phone[1:]
    if phone.startswith("0"):
        phone = "254" + phone[1:]
    return phone


def _access_token() -> str:
    url = f"{_base_url()}/oauth/v1/generate?grant_type=client_credentials"
    r = requests.get(
        url,
        auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET),
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _password(timestamp: str) -> str:
    raw = f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}"
    return base64.b64encode(raw.encode()).decode()


def initiate_stk_push(*, tenant, tenancy: Optional[Tenancy], amount: Decimal, phone: str) -> Payment:
    """Initiate an STK Push and create a Pending Payment row."""
    msisdn = _normalize_msisdn(phone)
    reference = f"AR-{uuid.uuid4().hex[:10].upper()}"
    paybill = str(getattr(settings, "MPESA_PAYBILL", settings.MPESA_SHORTCODE))
    account_number = str(getattr(settings, "MPESA_ACCOUNT_NUMBER", reference))
    payment = Payment.objects.create(
        tenant=tenant,
        tenancy=tenancy,
        amount=Decimal(amount),
        reference_number=reference,
        payment_method=Payment.Method.MPESA,
        phone_number=msisdn,
        balance_before=Decimal(tenancy.balance + tenancy.penalty) if tenancy else Decimal("0"),
        balance_after=Decimal(tenancy.balance + tenancy.penalty) if tenancy else Decimal("0"),
        status=Payment.Status.PENDING,
    )
    if not (settings.MPESA_CONSUMER_KEY and settings.MPESA_CONSUMER_SECRET):
        payment.status = Payment.Status.FAILED
        payment.notes = "M-Pesa credentials not configured."
        payment.save(update_fields=["status", "notes"])
        return payment

    try:
        token = _access_token()
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        payload = {
            "BusinessShortCode": settings.MPESA_SHORTCODE,
            "Password": _password(ts),
            "Timestamp": ts,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(Decimal(amount)),
            "PartyA": msisdn,
            "PartyB": paybill,
            "PhoneNumber": msisdn,
            "CallBackURL": settings.MPESA_CALLBACK_URL,
            "AccountReference": account_number,
            "TransactionDesc": f"Rent payment {reference}",
        }
        r = requests.post(
            f"{_base_url()}/mpesa/stkpush/v1/processrequest",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        data = r.json()
        payment.checkout_request_id = data.get("CheckoutRequestID", "")
        payment.merchant_request_id = data.get("MerchantRequestID", "")
        if data.get("ResponseCode") != "0":
            payment.status = Payment.Status.FAILED
            payment.notes = data.get("ResponseDescription") or str(data)
        payment.save()
    except Exception as e:  # network / API error
        logger.exception("STK push failed")
        payment.status = Payment.Status.FAILED
        payment.notes = f"Error: {e}"
        payment.save(update_fields=["status", "notes"])
    return payment


def apply_payment_to_tenancy(payment: Payment) -> Payment:
    """Deduct a successful payment from the tenancy: penalty first, then balance.

    A payment larger than what is owed leaves a negative balance (an overpayment
    credit). Safe to call from the Daraja callback or from manual verification.
    """
    tenancy = payment.tenancy
    if not tenancy:
        return payment
    tenancy = Tenancy.objects.select_for_update().get(pk=tenancy.pk)
    payment.balance_before = Decimal(tenancy.balance + tenancy.penalty)
    remaining = Decimal(payment.amount)
    if tenancy.penalty > 0:
        pay = min(tenancy.penalty, remaining)
        tenancy.penalty = tenancy.penalty - pay
        remaining -= pay
    if remaining > 0:
        tenancy.balance = tenancy.balance - remaining
    tenancy.last_payment_date = timezone.now()
    tenancy.save(update_fields=["balance", "penalty", "last_payment_date", "updated_at"])
    payment.balance_after = Decimal(tenancy.balance + tenancy.penalty)
    return payment


@transaction.atomic
def record_manual_paybill_payment(*, tenant, tenancy, amount: Decimal, mpesa_receipt: str) -> Payment:
    """Tenant paid directly on the Paybill (no STK push) and submitted the
    M-Pesa confirmation code. Stored as PENDING until an admin verifies it."""
    code = (mpesa_receipt or "").strip().upper()
    existing = Payment.objects.filter(mpesa_receipt=code).first()
    if code and existing:
        return existing
    return Payment.objects.create(
        tenant=tenant,
        tenancy=tenancy,
        amount=Decimal(amount),
        reference_number=f"MAN-{uuid.uuid4().hex[:10].upper()}",
        payment_method=Payment.Method.MPESA,
        mpesa_receipt=code,
        phone_number=_normalize_msisdn(getattr(tenant, "phone_number", "")),
        balance_before=Decimal(tenancy.balance + tenancy.penalty) if tenancy else Decimal("0"),
        balance_after=Decimal(tenancy.balance + tenancy.penalty) if tenancy else Decimal("0"),
        status=Payment.Status.PENDING,
        notes=f"Paybill {getattr(settings, 'MPESA_PAYBILL', '')} acct "
              f"{getattr(settings, 'MPESA_ACCOUNT_NUMBER', '')} - awaiting admin verification.",
    )


@transaction.atomic
def verify_manual_payment(payment: Payment) -> Payment:
    """Admin confirms a manual Paybill payment: mark SUCCESS and update balance."""
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if payment.status == Payment.Status.SUCCESS:
        return payment
    payment.status = Payment.Status.SUCCESS
    payment.transaction_date = timezone.now()
    apply_payment_to_tenancy(payment)
    payment.save()
    try:
        from notifications.services import notify_payment_received
        notify_payment_received(payment)
    except Exception:
        logger.exception("notify_payment_received failed")
    return payment


@transaction.atomic
def handle_callback(callback: dict) -> Optional[Payment]:
    """Process a Daraja STK callback payload. Returns the updated Payment.

    Handles duplicates (idempotent), failures, timeouts, cancellations.
    """
    stk = callback.get("Body", {}).get("stkCallback", {})
    checkout_id = stk.get("CheckoutRequestID", "")
    result_code = stk.get("ResultCode")
    result_desc = stk.get("ResultDesc", "")

    payment = (
        Payment.objects.select_for_update()
        .filter(checkout_request_id=checkout_id)
        .first()
    )
    if not payment:
        logger.warning("Callback for unknown CheckoutRequestID=%s", checkout_id)
        return None

    # Idempotent: already terminal.
    if payment.status in {Payment.Status.SUCCESS, Payment.Status.FAILED,
                          Payment.Status.CANCELLED, Payment.Status.TIMEOUT}:
        return payment

    if result_code == 0:
        items = {
            i["Name"]: i.get("Value")
            for i in stk.get("CallbackMetadata", {}).get("Item", [])
            if "Name" in i
        }
        payment.mpesa_receipt = str(items.get("MpesaReceiptNumber", ""))
        payment.amount = Decimal(str(items.get("Amount", payment.amount)))
        payment.phone_number = str(items.get("PhoneNumber", payment.phone_number))
        payment.status = Payment.Status.SUCCESS
        payment.transaction_date = timezone.now()
        payment.notes = result_desc

        apply_payment_to_tenancy(payment)
        payment.save()

        try:
            from notifications.services import notify_payment_received
            notify_payment_received(payment)
        except Exception:
            logger.exception("notify_payment_received failed")
    else:
        # Map common Daraja result codes.
        if result_code == 1032:
            payment.status = Payment.Status.CANCELLED
        elif result_code == 1037:
            payment.status = Payment.Status.TIMEOUT
        else:
            payment.status = Payment.Status.FAILED
        payment.notes = f"{result_code}: {result_desc}"
        payment.save(update_fields=["status", "notes"])

    return payment
