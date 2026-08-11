"""Business logic for tenancy: approvals, prorated rent, billing, penalties."""
from calendar import monthrange
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta
from typing import Optional

from django.db import transaction
from django.utils import timezone

from apartments.models import Room
from .models import RoomRequest, Tenancy


def _q(amount: Decimal) -> Decimal:
    """Quantize a Decimal to 2 places."""
    return Decimal(amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def prorated_first_balance(monthly_rent: Decimal, move_in: date) -> Decimal:
    """Rent for the remainder of the move-in month.

    If the tenant moves in on the 1st, the full monthly rent applies.
    Otherwise: daily_rate = monthly_rent / days_in_month, charged for the
    remaining days (inclusive of the move-in day).
    """
    days_in_month = monthrange(move_in.year, move_in.month)[1]
    if move_in.day == 1:
        return _q(monthly_rent)
    remaining_days = days_in_month - move_in.day + 1
    daily = Decimal(monthly_rent) / Decimal(days_in_month)
    return _q(daily * Decimal(remaining_days))


def next_month_first(d: date) -> date:
    """Return the 1st day of the month AFTER d."""
    year = d.year + (1 if d.month == 12 else 0)
    month = 1 if d.month == 12 else d.month + 1
    return date(year, month, 1)


@transaction.atomic
def approve_room_request(req: RoomRequest, reviewer, admin_note: str = "") -> Tenancy:
    """Approve a room request: free any old room, create the new tenancy."""
    if req.status != RoomRequest.Status.PENDING:
        raise ValueError("Only pending requests can be approved.")

    tenant = req.tenant
    room = Room.objects.select_for_update().get(pk=req.room_id)
    if not room.is_vacant:
        raise ValueError("Selected room is no longer vacant.")

    # 1) Free any existing tenancy for this tenant.
    old = Tenancy.objects.select_for_update().filter(tenant=tenant, active=True).first()
    carried_balance = Decimal("0")
    carried_penalty = Decimal("0")
    if old:
        # Carry any credit (negative balance) and unpaid penalty to the new room.
        carried_balance = min(Decimal(old.balance or 0), Decimal("0"))
        carried_penalty = Decimal(old.penalty or 0)
        old_room = Room.objects.select_for_update().get(pk=old.room_id)
        old_room.tenant = None
        old_room.save(update_fields=["tenant"])
        old.active = False
        old.balance = Decimal("0")
        old.penalty = Decimal("0")
        old.save(update_fields=["active", "balance", "penalty", "updated_at"])

    # 2) Create the new tenancy with prorated first balance, less any credit.
    move_in = timezone.localdate()
    first_balance = _q(prorated_first_balance(room.monthly_rent, move_in) + carried_balance)
    tenancy = Tenancy.objects.create(
        tenant=tenant,
        room=room,
        move_in_date=move_in,
        monthly_rent=room.monthly_rent,
        balance=first_balance,
        penalty=_q(carried_penalty),
        next_due_date=next_month_first(move_in),
        active=True,
    )

    # 3) Attach tenant to room.
    room.tenant = tenant
    room.save(update_fields=["tenant"])

    # 4) Update the request.
    req.status = RoomRequest.Status.APPROVED
    req.admin_note = admin_note
    req.reviewed_by = reviewer
    req.reviewed_at = timezone.now()
    req.save(update_fields=["status", "admin_note", "reviewed_by", "reviewed_at"])

    # 5) Notify (best-effort).
    try:
        from notifications.services import notify_room_approved
        notify_room_approved(tenant, tenancy)
    except Exception:
        pass

    return tenancy


@transaction.atomic
def reject_room_request(req: RoomRequest, reviewer, admin_note: str = "") -> RoomRequest:
    if req.status != RoomRequest.Status.PENDING:
        raise ValueError("Only pending requests can be rejected.")
    req.status = RoomRequest.Status.REJECTED
    req.admin_note = admin_note
    req.reviewed_by = reviewer
    req.reviewed_at = timezone.now()
    req.save(update_fields=["status", "admin_note", "reviewed_by", "reviewed_at"])
    return req


@transaction.atomic
def run_monthly_billing(today: Optional[date] = None) -> int:
    """Add monthly rent to every active tenancy. Reset penalty flag."""
    today = today or timezone.localdate()
    updated = 0
    for tenancy in Tenancy.objects.select_for_update().filter(active=True):
        tenancy.balance = _q(Decimal(tenancy.balance) + Decimal(tenancy.monthly_rent))
        tenancy.next_due_date = next_month_first(today)
        tenancy.penalty_applied_month = ""  # allow one penalty in the new month
        tenancy.save(update_fields=["balance", "next_due_date", "penalty_applied_month", "updated_at"])
        updated += 1
        try:
            from notifications.services import notify_rent_posted
            notify_rent_posted(tenancy)
        except Exception:
            pass
    return updated


@transaction.atomic
def apply_late_penalties(today: Optional[date] = None, penalty_pct: Decimal = Decimal("0.10")) -> int:
    """Apply late penalty on the 11th to any tenancy with a positive balance.

    Penalty applied at most once per month per tenancy.
    """
    today = today or timezone.localdate()
    month_key = today.strftime("%Y-%m")
    charged = 0
    for tenancy in Tenancy.objects.select_for_update().filter(active=True, balance__gt=0):
        if tenancy.penalty_applied_month == month_key:
            continue
        penalty = _q(Decimal(tenancy.monthly_rent) * penalty_pct)
        tenancy.penalty = _q(Decimal(tenancy.penalty) + penalty)
        tenancy.penalty_applied_month = month_key
        tenancy.save(update_fields=["penalty", "penalty_applied_month", "updated_at"])
        charged += 1
        try:
            from notifications.services import notify_penalty_applied
            notify_penalty_applied(tenancy, penalty)
        except Exception:
            pass
    return charged
