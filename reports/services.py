"""Report generation: CSV, Excel, PDF exports."""
import csv
from decimal import Decimal
from io import BytesIO

from django.db.models import Sum, Q
from django.http import HttpResponse
from django.utils import timezone
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from apartments.models import Apartment, Room
from payments.models import Payment
from tenancy.models import Tenancy
from accounts.models import User


REPORTS = {
    "rent_collection": "Monthly Rent Collection",
    "outstanding": "Outstanding Balances",
    "vacant_rooms": "Vacant Rooms",
    "occupied_rooms": "Occupied Rooms",
    "payments_by_month": "Payments by Month",
    "payments_by_apartment": "Payments by Apartment",
    "late_payments": "Late Payments",
    "tenants": "Tenant List",
}


def _rows_for(kind: str):
    """Return (headers, rows) for a given report."""
    now = timezone.now()
    if kind == "rent_collection":
        qs = Payment.objects.filter(
            status=Payment.Status.SUCCESS,
            transaction_date__year=now.year, transaction_date__month=now.month,
        ).select_related("tenant", "tenancy", "tenancy__room__apartment")
        headers = ["Date", "Receipt", "Tenant", "Apartment", "Room", "Amount"]
        rows = [
            [p.transaction_date.strftime("%Y-%m-%d"), p.reference_number,
             p.tenant.full_name,
             getattr(getattr(getattr(p.tenancy, "room", None), "apartment", None), "name", ""),
             getattr(getattr(p.tenancy, "room", None), "room_number", ""),
             float(p.amount)]
            for p in qs
        ]
        return headers, rows

    if kind == "outstanding":
        qs = Tenancy.objects.filter(active=True, balance__gt=0).select_related("tenant", "room__apartment")
        headers = ["Tenant", "Phone", "Apartment", "Room", "Balance", "Penalty", "Total Due"]
        rows = [[t.tenant.full_name, t.tenant.phone_number, t.room.apartment.name,
                 t.room.room_number, float(t.balance), float(t.penalty),
                 float(Decimal(t.balance) + Decimal(t.penalty))] for t in qs]
        return headers, rows

    if kind == "vacant_rooms":
        qs = Room.objects.filter(tenant__isnull=True).select_related("apartment")
        headers = ["Apartment", "Room", "Floor", "Type", "Rent"]
        rows = [[r.apartment.name, r.room_number, r.floor, r.get_room_type_display(),
                 float(r.monthly_rent)] for r in qs]
        return headers, rows

    if kind == "occupied_rooms":
        qs = Room.objects.filter(tenant__isnull=False).select_related("apartment", "tenant")
        headers = ["Apartment", "Room", "Tenant", "Phone", "Rent"]
        rows = [[r.apartment.name, r.room_number, r.tenant.full_name,
                 r.tenant.phone_number, float(r.monthly_rent)] for r in qs]
        return headers, rows

    if kind == "payments_by_month":
        agg = (Payment.objects.filter(status=Payment.Status.SUCCESS)
               .extra(select={"month": "TO_CHAR(transaction_date, 'YYYY-MM')"})
               .values("month").annotate(total=Sum("amount")).order_by("month"))
        headers = ["Month", "Total Collected"]
        rows = [[r["month"], float(r["total"] or 0)] for r in agg]
        return headers, rows

    if kind == "payments_by_apartment":
        agg = (Payment.objects.filter(status=Payment.Status.SUCCESS)
               .values("tenancy__room__apartment__name")
               .annotate(total=Sum("amount")).order_by("tenancy__room__apartment__name"))
        headers = ["Apartment", "Total Collected"]
        rows = [[r["tenancy__room__apartment__name"] or "-", float(r["total"] or 0)] for r in agg]
        return headers, rows

    if kind == "late_payments":
        qs = Tenancy.objects.filter(active=True, penalty__gt=0).select_related("tenant", "room__apartment")
        headers = ["Tenant", "Phone", "Apartment", "Room", "Balance", "Penalty"]
        rows = [[t.tenant.full_name, t.tenant.phone_number, t.room.apartment.name,
                 t.room.room_number, float(t.balance), float(t.penalty)] for t in qs]
        return headers, rows

    if kind == "tenants":
        qs = User.objects.filter(role=User.Role.TENANT).prefetch_related("tenancy_set__room__apartment")
        headers = ["Name", "Phone", "ID Number", "Email", "Role", "Active",
                   "Apartment", "Room", "Monthly Rent", "Balance", "Penalty",
                   "Move-in Date", "Joined"]
        rows = []
        for u in qs:
            tenancy = u.tenancy_set.filter(active=True).select_related("room__apartment").first()
            if tenancy:
                apt = tenancy.room.apartment.name
                room = tenancy.room.room_number
                rent = float(tenancy.monthly_rent)
                bal = float(tenancy.balance)
                pen = float(tenancy.penalty)
                movein = tenancy.move_in_date.strftime("%Y-%m-%d")
            else:
                apt = room = ""; rent = bal = pen = 0.0; movein = ""
            rows.append([
                u.full_name, u.phone_number, u.id_number, u.email or "",
                u.get_role_display() if hasattr(u, "get_role_display") else u.role,
                "Yes" if u.is_active else "No",
                apt, room, rent, bal, pen, movein,
                u.date_joined.strftime("%Y-%m-%d"),
            ])
        return headers, rows

    return ["Info"], [["Unknown report"]]


def as_csv(kind: str) -> HttpResponse:
    headers, rows = _rows_for(kind)
    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = f'attachment; filename="{kind}.csv"'
    writer = csv.writer(resp)
    writer.writerow(headers)
    writer.writerows(rows)
    return resp


def as_xlsx(kind: str) -> HttpResponse:
    headers, rows = _rows_for(kind)
    wb = Workbook()
    ws = wb.active
    ws.title = REPORTS.get(kind, "Report")[:31]
    ws.append(headers)
    for r in rows:
        ws.append(r)
    buf = BytesIO()
    wb.save(buf)
    resp = HttpResponse(buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = f'attachment; filename="{kind}.xlsx"'
    return resp


def as_pdf(kind: str) -> HttpResponse:
    headers, rows = _rows_for(kind)
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                            leftMargin=1 * cm, rightMargin=1 * cm,
                            topMargin=1 * cm, bottomMargin=1 * cm)
    styles = getSampleStyleSheet()
    elements = [Paragraph(REPORTS.get(kind, "Report"), styles["Title"]), Spacer(1, 12)]
    data = [headers] + [[str(c) for c in r] for r in rows]
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d6efd")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.whitesmoke, colors.white]),
    ]))
    elements.append(t)
    doc.build(elements)
    resp = HttpResponse(buf.getvalue(), content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{kind}.pdf"'
    return resp
