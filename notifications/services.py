"""SMS + Email + in-app notification services."""
from __future__ import annotations

import logging
from typing import Optional

from django.conf import settings
from django.core.mail import send_mail

from .models import NotificationLog, Notification, Announcement, AnnouncementAudience

logger = logging.getLogger(__name__)


def _log(*, user, channel, recipient, body, subject="", status=NotificationLog.Status.SENT, error=""):
    try:
        NotificationLog.objects.create(
            user=user, channel=channel, recipient=recipient, body=body,
            subject=subject, status=status, error=error,
        )
    except Exception:
        logger.exception("Failed to write NotificationLog")


def push_notification(user, title: str, body: str = "", *,
                      category: str = Notification.Category.SYSTEM, url: str = "") -> Optional[Notification]:
    if not user:
        return None
    try:
        return Notification.objects.create(
            user=user, title=title, body=body, category=category, url=url,
        )
    except Exception:
        logger.exception("Failed to create in-app Notification")
        return None


def send_sms(phone: str, message: str, user=None) -> bool:
    if not phone or not message:
        return False
    if not settings.AT_API_KEY:
        _log(user=user, channel=NotificationLog.Channel.SMS, recipient=phone,
             body=message, status=NotificationLog.Status.FAILED,
             error="SMS provider not configured; message not sent.")
        return False
    try:
        import africastalking
        africastalking.initialize(settings.AT_USERNAME, settings.AT_API_KEY)
        sms = africastalking.SMS
        kwargs = {}
        if settings.AT_SENDER_ID:
            kwargs["sender_id"] = settings.AT_SENDER_ID
        sms.send(message, [phone], **kwargs)
        _log(user=user, channel=NotificationLog.Channel.SMS, recipient=phone, body=message)
        return True
    except Exception as e:
        logger.exception("SMS send failed")
        _log(user=user, channel=NotificationLog.Channel.SMS, recipient=phone,
             body=message, status=NotificationLog.Status.FAILED, error=str(e))
        return False


def send_email(email: Optional[str], subject: str, message: str, user=None) -> bool:
    if not email:
        return False
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
        _log(user=user, channel=NotificationLog.Channel.EMAIL, recipient=email,
             body=message, subject=subject)
        return True
    except Exception as e:
        logger.exception("Email send failed")
        _log(user=user, channel=NotificationLog.Channel.EMAIL, recipient=email or "",
             body=message, subject=subject, status=NotificationLog.Status.FAILED, error=str(e))
        return False


# ---- High-level event helpers ---------------------------------------------

def _admins():
    from accounts.models import User
    return User.objects.filter(role=User.Role.ADMIN)


def notify_registration(user):
    msg = f"Hello {user.full_name}, welcome to {settings.LANDLORD_NAME}. Your account has been created."
    send_sms(user.phone_number, msg, user=user)
    send_email(user.email, "Welcome", msg, user=user)
    # notify admins
    for admin in _admins():
        push_notification(
            admin, "New tenant registered",
            f"{user.full_name} ({user.phone_number}) just registered.",
            category=Notification.Category.REGISTRATION,
        )


def notify_room_approved(user, tenancy):
    room = tenancy.room
    msg = (
        f"Hi {user.full_name}, your room request has been approved. "
        f"Room: {room.room_number} at {room.apartment.name}. "
        f"Monthly rent: KES {tenancy.monthly_rent}. Initial balance: KES {tenancy.balance}."
    )
    send_sms(user.phone_number, msg, user=user)
    send_email(user.email, "Room Approved", msg, user=user)
    push_notification(
        user, "Room request approved", msg,
        category=Notification.Category.REQUEST,
    )
    for admin in _admins():
        push_notification(
            admin, "New tenancy created",
            f"{user.full_name} now occupies {room.apartment.name} - {room.room_number}.",
            category=Notification.Category.TENANCY,
        )


def notify_room_rejected(user, request_obj):
    msg = f"Your room request for {request_obj.room} was rejected. {request_obj.admin_note}"
    push_notification(user, "Room request rejected", msg, category=Notification.Category.REQUEST)


def notify_rent_posted(tenancy):
    u = tenancy.tenant
    msg = (f"Hi {u.full_name}, rent of KES {tenancy.monthly_rent} has been posted for this month. "
           f"Current balance: KES {tenancy.balance}. Due by 10th.")
    send_sms(u.phone_number, msg, user=u)
    send_email(u.email, "Rent Posted", msg, user=u)
    push_notification(u, "Rent posted", msg, category=Notification.Category.PAYMENT)


def notify_payment_reminder(tenancy):
    u = tenancy.tenant
    msg = (f"Reminder: Rent of KES {tenancy.balance} due by 10th. "
           f"Pay via the tenant portal.")
    send_sms(u.phone_number, msg, user=u)
    push_notification(u, "Payment reminder", msg, category=Notification.Category.PAYMENT)


def notify_late_reminder(tenancy):
    u = tenancy.tenant
    msg = (f"Final reminder: Rent of KES {tenancy.balance} is due today. "
           f"Late penalty applies from tomorrow.")
    send_sms(u.phone_number, msg, user=u)
    push_notification(u, "Late payment reminder", msg, category=Notification.Category.PAYMENT)


def notify_penalty_applied(tenancy, penalty_amount):
    u = tenancy.tenant
    total_due = tenancy.balance + tenancy.penalty
    msg = (f"A late-payment penalty of KES {penalty_amount} has been added to your balance. "
           f"Your outstanding balance is now KES {total_due}.")
    send_sms(u.phone_number, msg, user=u)
    push_notification(u, "Penalty applied", msg, category=Notification.Category.PAYMENT)
    # Also drop a direct message so it lives in the thread
    try:
        _post_admin_message(u, msg)
    except Exception:
        pass


def notify_payment_received(payment):
    u = payment.tenant
    msg = (f"Payment received: KES {payment.amount}. Receipt: {payment.reference_number}. "
           f"New balance: KES {payment.balance_after}.")
    send_sms(u.phone_number, msg, user=u)
    send_email(u.email, f"Receipt {payment.reference_number}", msg, user=u)
    push_notification(u, f"Payment {payment.get_status_display()}", msg,
                      category=Notification.Category.PAYMENT)
    for admin in _admins():
        push_notification(
            admin, "New payment received",
            f"{u.full_name} paid KES {payment.amount} ({payment.reference_number}).",
            category=Notification.Category.PAYMENT,
        )


def notify_payment_status(payment):
    """Non-success status updates (pending / failed / cancelled)."""
    u = payment.tenant
    if not u:
        return
    msg = f"Your payment of KES {payment.amount} is {payment.get_status_display()}."
    push_notification(u, f"Payment {payment.get_status_display()}", msg,
                      category=Notification.Category.PAYMENT)


def notify_vacate_declared(tenancy, vacate_date):
    """Tell every admin that a tenant has confirmed a vacate date."""
    for admin in _admins():
        push_notification(
            admin, "Tenant confirmed vacate date",
            f"{tenancy.tenant.full_name} (Room {tenancy.room.room_number}, "
            f"{tenancy.room.apartment.name}) will vacate on {vacate_date}.",
            category=Notification.Category.TENANCY,
        )


def send_balance_reminder(tenancy, sender):
    """Admin -> tenant reminder to clear an outstanding balance."""
    u = tenancy.tenant
    body = (
        f"Hi {u.full_name}, this is a friendly reminder to clear your outstanding "
        f"balance of KES {tenancy.total_due} to avoid late-payment penalties."
    )
    _post_admin_message(u, body, sender=sender)
    push_notification(u, "Balance reminder", body, category=Notification.Category.PAYMENT)
    send_sms(u.phone_number, body, user=u)


def broadcast_announcement(sender, audience: str, title: str, body: str,
                           apartment=None, tenant=None) -> int:
    """Persist an Announcement + push in-app notifications to the right users."""
    from accounts.models import User
    from tenancy.models import Tenancy

    Announcement.objects.create(
        sender=sender, audience=audience, title=title, body=body,
        apartment=apartment, tenant=tenant,
    )
    if audience == AnnouncementAudience.TENANT and tenant:
        recipients = [tenant]
    elif audience == AnnouncementAudience.APARTMENT and apartment:
        tenant_ids = Tenancy.objects.filter(active=True, room__apartment=apartment)\
            .values_list("tenant_id", flat=True)
        recipients = User.objects.filter(id__in=list(tenant_ids))
    else:
        recipients = User.objects.filter(role=User.Role.TENANT)
    n = 0
    for u in recipients:
        push_notification(u, title, body, category=Notification.Category.ANNOUNCEMENT)
        n += 1
    return n


def _post_admin_message(tenant_user, body: str, sender=None):
    """Post a message from admin into the tenant's thread (creates thread if needed)."""
    from .models import MessageThread, Message
    thread, _ = MessageThread.objects.get_or_create(tenant=tenant_user)
    Message.objects.create(thread=thread, sender=sender, body=body)
    thread.save(update_fields=["updated_at"])
    return thread
