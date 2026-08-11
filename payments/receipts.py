"""PDF receipt generation using ReportLab."""
from decimal import Decimal
from io import BytesIO

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
)


def build_receipt_pdf(payment) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
        title=f"Receipt {payment.reference_number}",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("t", parent=styles["Title"], fontSize=18, spaceAfter=8)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12, spaceAfter=6)
    small = ParagraphStyle("s", parent=styles["Normal"], fontSize=9, textColor=colors.grey)

    tenancy = payment.tenancy
    room = getattr(tenancy, "room", None)
    apartment = getattr(room, "apartment", None)

    elements = [
        Paragraph(settings.LANDLORD_NAME, title),
        Paragraph(
            f"{settings.LANDLORD_PHONE} · {settings.LANDLORD_EMAIL}", small
        ),
        Spacer(1, 12),
        Paragraph("Payment Receipt", h2),
    ]

    info = [
        ["Receipt Number:", payment.reference_number],
        ["M-Pesa Reference:", payment.mpesa_receipt or "-"],
        ["Date:", payment.transaction_date.strftime("%Y-%m-%d %H:%M")],
        ["Tenant:", payment.tenant.full_name],
        ["Phone:", payment.tenant.phone_number],
        ["Apartment:", apartment.name if apartment else "-"],
        ["Room:", room.room_number if room else "-"],
        ["Amount:", f"KES {Decimal(payment.amount):,.2f}"],
        ["Balance Before:", f"KES {Decimal(payment.balance_before):,.2f}"],
        ["Balance Remaining:", f"KES {Decimal(payment.balance_after):,.2f}"],
        ["Status:", payment.get_status_display()],
    ]
    t = Table(info, colWidths=[5 * cm, 10 * cm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.lightgrey),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 18))
    elements.append(Paragraph(
        "Thank you for your payment. This is a computer-generated receipt.", small
    ))

    doc.build(elements)
    return buf.getvalue()
