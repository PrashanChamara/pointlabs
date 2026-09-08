"""Private, server-side Pointlabs HR document generation.

The generated files live under Flask's instance directory rather than the static
directory.  A route must therefore authorize a request before returning a file.
"""

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from html import escape
from pathlib import Path
import os
import re
import secrets

from flask import current_app
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


INK = colors.HexColor("#17241D")
MUTED = colors.HexColor("#66766B")
MINT = colors.HexColor("#F3F9F3")
MINT_DARK = colors.HexColor("#E3F0E5")
GOLD = colors.HexColor("#C8942B")
GOLD_SOFT = colors.HexColor("#FFF3D5")
LINE = colors.HexColor("#D9E4DA")
WHITE = colors.white


def _generated_dir(kind):
    folder = Path(current_app.instance_path) / "generated" / kind
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def payslip_pdf_path(stored_path):
    """Return a trusted private path for a persisted payslip PDF reference."""
    return _generated_dir("payslips") / Path(stored_path or "").name


def leave_confirmation_pdf_path(stored_path):
    """Return a trusted private path for a persisted leave PDF reference."""
    return _generated_dir("leave-confirmations") / Path(stored_path or "").name


def _money(value, currency):
    amount = Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{currency} {amount:,.2f}"


def _number_words(value):
    """Human-readable whole-number wording for payslip net amounts."""
    number = int(Decimal(value or 0).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if number == 0:
        return "Zero"
    if number < 0:
        return "Minus " + _number_words(-number)
    small = ("", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
             "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
             "Seventeen", "Eighteen", "Nineteen")
    tens = ("", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety")

    def under_thousand(value):
        parts = []
        if value >= 100:
            parts.append(f"{small[value // 100]} Hundred")
            value %= 100
        if value >= 20:
            parts.append(tens[value // 10] + (f"-{small[value % 10]}" if value % 10 else ""))
        elif value:
            parts.append(small[value])
        return " ".join(parts)

    groups = ((1_000_000_000, "Billion"), (1_000_000, "Million"), (1_000, "Thousand"))
    result = []
    for divisor, label in groups:
        if number >= divisor:
            result.append(f"{under_thousand(number // divisor)} {label}")
            number %= divisor
    if number:
        result.append(under_thousand(number))
    return " ".join(result)


def _safe_display(value, fallback):
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "", value or "")
    return cleaned or fallback


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("PointlabsTitle", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=19, leading=23, textColor=INK, spaceAfter=2),
        "section": ParagraphStyle("PointlabsSection", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=GOLD, spaceAfter=6, tracking=1.2),
        "label": ParagraphStyle("PointlabsLabel", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=7, leading=9, textColor=MUTED, tracking=.7),
        "value": ParagraphStyle("PointlabsValue", parent=base["Normal"], fontName="Helvetica", fontSize=9, leading=12, textColor=INK),
        "value_bold": ParagraphStyle("PointlabsValueBold", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=INK),
        "right": ParagraphStyle("PointlabsRight", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=INK, alignment=TA_RIGHT),
        "note": ParagraphStyle("PointlabsNote", parent=base["Normal"], fontName="Helvetica", fontSize=8, leading=11, textColor=MUTED),
        "net_label": ParagraphStyle("PointlabsNetLabel", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=INK, tracking=.8),
        "net": ParagraphStyle("PointlabsNet", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=INK, alignment=TA_RIGHT),
        "approved": ParagraphStyle("PointlabsApproved", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=colors.HexColor("#1A6B48"), alignment=TA_CENTER),
        "statement": ParagraphStyle("PointlabsStatement", parent=base["Normal"], fontName="Helvetica", fontSize=9, leading=14, textColor=INK),
    }


def _paragraph(text, style):
    return Paragraph(escape(str(text or "—")).replace("\n", "<br/>"), style)


def _company_for(payslip, profile):
    if payslip.template_country == "AE":
        return "Pointlabs Technologies Ltd"
    return "Pointlabs Technologies Pvt Ltd"


def _logo():
    logo = Path(current_app.static_folder) / "images" / "logo-light.png"
    if logo.is_file():
        image = Image(str(logo), width=37 * mm, height=7.9 * mm)
        image.hAlign = "LEFT"
        return image
    return None


def _footer(canvas, doc):
    canvas.saveState()
    page_width, _ = A4
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(.5)
    canvas.line(doc.leftMargin, 15 * mm, page_width - doc.rightMargin, 15 * mm)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7.3)
    canvas.drawString(doc.leftMargin, 10 * mm, "Pointlabs One · Confidential HR document")
    canvas.drawRightString(page_width - doc.rightMargin, 10 * mm, f"Generated {datetime.utcnow():%d %b %Y %H:%M UTC}  ·  Page {doc.page}")
    canvas.restoreState()


def _document(target):
    return SimpleDocTemplate(
        str(target), pagesize=A4, rightMargin=17 * mm, leftMargin=17 * mm,
        topMargin=16 * mm, bottomMargin=23 * mm, title="Pointlabs One HR document",
        author="Pointlabs Technologies", pageCompression=0,
    )


def _write_pdf(folder, prefix, build_story):
    target = folder / f"{prefix}-{secrets.token_urlsafe(18)}.pdf"
    temporary = target.with_suffix(".tmp")
    try:
        document = _document(temporary)
        document.build(build_story(), onFirstPage=_footer, onLaterPages=_footer)
        os.replace(temporary, target)
    except Exception:
        temporary.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        raise
    return target.name, target


def _document_header(title, subtitle, styles, reference=None, status=None):
    logo = _logo()
    left = [logo] if logo else [_paragraph("Pointlabs <b>One</b>", styles["value_bold"])]
    left.extend([Spacer(1, 3 * mm), _paragraph(title, styles["title"]), _paragraph(subtitle, styles["note"])])
    right = []
    if status:
        badge = Table([[_paragraph(status, styles["approved"])]], colWidths=[31 * mm], rowHeights=[8 * mm])
        badge.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), MINT_DARK), ("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#B9DBC5")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        right.append(badge)
    if reference:
        right.extend([Spacer(1, 3 * mm), _paragraph("REFERENCE", styles["label"]), _paragraph(reference, styles["right"])])
    header = Table([[left, right]], colWidths=[112 * mm, 58 * mm])
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (1, 0), "RIGHT")]))
    return [header, Spacer(1, 7 * mm), HRFlowable(width="100%", thickness=1, color=LINE), Spacer(1, 6 * mm)]


def _information_table(entries, styles, columns=2):
    cells = []
    for label, value in entries:
        cells.append([_paragraph(label.upper(), styles["label"]), _paragraph(value, styles["value_bold"])])
    rows = []
    per_row = columns
    for index in range(0, len(cells), per_row):
        row = cells[index:index + per_row]
        while len(row) < per_row:
            row.append([_paragraph("", styles["label"]), _paragraph("", styles["value"])])
        rows.append(row)
    flattened = []
    for row in rows:
        labels, values = zip(*row)
        flattened.append(list(labels))
        flattened.append(list(values))
    # The content width is 170 mm (A4 less the configured margins).  Size each
    # table column from that width so the optional three-column leave-balance
    # section never overflows the printable page.
    table = Table(flattened, colWidths=[(170 * mm) / columns] * columns, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), MINT),
        ("BOX", (0, 0), (-1, -1), .5, LINE),
        ("INNERGRID", (0, 0), (-1, -1), .25, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return table


def _salary_table(title, rows, total_label, total_value, styles):
    data = [[_paragraph(title.upper(), styles["section"]), ""]]
    data.extend([[_paragraph(label, styles["value"]), _paragraph(value, styles["right"])] for label, value in rows])
    data.append([_paragraph(total_label, styles["value_bold"]), _paragraph(total_value, styles["right"])])
    table = Table(data, colWidths=[54 * mm, 31 * mm])
    total_row = len(data) - 1
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), MINT_DARK),
        ("SPAN", (0, 0), (1, 0)),
        ("BACKGROUND", (0, total_row), (-1, total_row), GOLD_SOFT),
        ("BOX", (0, 0), (-1, -1), .5, LINE),
        ("INNERGRID", (0, 1), (-1, -2), .25, LINE),
        ("LINEABOVE", (0, total_row), (-1, total_row), .8, GOLD),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return table


def generate_payslip_pdf(payslip):
    """Create one branded, A4 PDF for the supplied immutable payslip version."""
    styles = _styles()
    profile = payslip.user.employee_profile
    period = datetime(payslip.payroll_year, payslip.payroll_month, 1).strftime("%B %Y")
    employee_code = _safe_display(profile.employee_code if profile else None, f"EMP{payslip.user_id:03d}")
    display_name = f"Pointlabs_Payslip_{payslip.payroll_year}-{payslip.payroll_month:02d}_{employee_code}.pdf"

    def story():
        company = _company_for(payslip, profile)
        output = _document_header("PAYSLIP", period, styles, reference=f"PAY-{payslip.payroll_year}{payslip.payroll_month:02d}-V{payslip.version}")
        output += [_paragraph("EMPLOYEE DETAILS", styles["section"])]
        output += [_information_table([
            ("Employee name", profile.full_name if profile else payslip.user.username),
            ("Employee code", profile.employee_code if profile and profile.employee_code else "—"),
            ("Designation", profile.designation.name if profile and profile.designation else "—"),
            ("Department", profile.department.name if profile and profile.department else "—"),
            ("Location", profile.location.name if profile and profile.location else "—"),
            ("Date joined", profile.date_of_joining.strftime("%d %b %Y") if profile and profile.date_of_joining else "—"),
        ], styles), Spacer(1, 7 * mm)]
        earnings = [
            ("Basic Salary", _money(payslip.basic_salary, payslip.currency)),
            ("Allowances", _money(payslip.allowances, payslip.currency)),
            ("Other Earnings", _money(payslip.other_earnings, payslip.currency)),
        ]
        deductions = []
        if payslip.template_country == "LK":
            deductions.extend([
                ("WHT", _money(payslip.wht, payslip.currency)),
                ("EPF", _money(payslip.epf, payslip.currency)),
                ("ETF", _money(payslip.etf, payslip.currency)),
                ("PAYE", _money(payslip.paye, payslip.currency)),
            ])
        # UAE payslips intentionally use the supplied simpler deduction structure.
        # Any recorded UAE payroll deduction therefore rolls into its single
        # "Other Deductions" line so the visible line items always reconcile to
        # the stored total rather than presenting a misleading total.
        other_deductions = payslip.total_deductions if payslip.template_country == "AE" else payslip.other_deductions
        deductions.append(("Other Deductions", _money(other_deductions, payslip.currency)))
        salary = Table([[_salary_table("Earnings", earnings, "Gross Salary", _money(payslip.gross_salary, payslip.currency), styles), _salary_table("Deductions", deductions, "Total Deductions", _money(payslip.total_deductions, payslip.currency), styles)]], colWidths=[85 * mm, 85 * mm])
        salary.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        output += [KeepTogether(salary), Spacer(1, 7 * mm)]
        net = Table([[
            [_paragraph("NET SALARY PAYABLE", styles["net_label"]), _paragraph(f"{_number_words(payslip.net_salary)} {payslip.currency} only", styles["note"])],
            _paragraph(_money(payslip.net_salary, payslip.currency), styles["net"]),
        ]], colWidths=[98 * mm, 72 * mm])
        net.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), GOLD_SOFT), ("BOX", (0, 0), (-1, -1), .7, GOLD), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9), ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9)]))
        output += [net, Spacer(1, 7 * mm), _paragraph(f"Issued by {company}. This is a system-generated payslip and does not require a physical signature.", styles["note"])]
        return output

    stored_path, _ = _write_pdf(_generated_dir("payslips"), f"payslip-{payslip.id}-v{payslip.version}", story)
    return stored_path, display_name


def generate_leave_confirmation_pdf(leave_request):
    """Create the official PDF only for a final approved leave request."""
    if leave_request.status != "approved":
        raise ValueError("Leave confirmation can only be generated for approved leave.")
    if not leave_request.confirmation_reference:
        year = leave_request.approver.created_at.year if getattr(leave_request.approver, "created_at", None) else datetime.utcnow().year
        leave_request.confirmation_reference = f"PL-LEAVE-{year}-{secrets.token_hex(5).upper()}"
    styles = _styles()
    profile = leave_request.user.employee_profile
    approver = leave_request.approver
    employee_code = _safe_display(profile.employee_code if profile else None, f"EMP{leave_request.user_id:03d}")
    display_name = f"Pointlabs_Leave_Confirmation_{leave_request.start_date:%Y%m%d}_{employee_code}.pdf"

    def story():
        output = _document_header("LEAVE CONFIRMATION", "Official leave approval record", styles, leave_request.confirmation_reference, "APPROVED")
        output += [_paragraph("EMPLOYEE DETAILS", styles["section"])]
        output += [_information_table([
            ("Employee name", profile.full_name if profile else leave_request.user.username),
            ("Employee code", profile.employee_code if profile and profile.employee_code else "—"),
            ("Designation", profile.designation.name if profile and profile.designation else "—"),
            ("Department", profile.department.name if profile and profile.department else "—"),
            ("Location", profile.location.name if profile and profile.location else "—"),
            ("Employment status", profile.employment_status.title() if profile and profile.employment_status else "Active"),
        ], styles), Spacer(1, 7 * mm), _paragraph("LEAVE DETAILS", styles["section"])]
        output += [_information_table([
            ("Leave type", leave_request.leave_type.name),
            ("Approval status", "Approved"),
            ("Leave start date", leave_request.start_date.strftime("%d %b %Y")),
            ("Leave end date", leave_request.end_date.strftime("%d %b %Y")),
            ("Number of leave days", f"{leave_request.days:g} working days"),
            ("Applied date", leave_request.created_at.strftime("%d %b %Y")),
            ("Approved date", leave_request.updated_at.strftime("%d %b %Y")),
            ("Approver", profile.reporting_officer.employee_profile.full_name if profile and profile.reporting_officer and profile.reporting_officer.employee_profile else (approver.employee_profile.full_name if approver and approver.employee_profile else "Pointlabs HR")),
            ("Approver designation", approver.employee_profile.designation.name if approver and approver.employee_profile and approver.employee_profile.designation else "—"),
            ("Approval note", leave_request.reviewer_comment or "—"),
        ], styles), Spacer(1, 7 * mm)]
        from app.models.hr import LeaveBalance

        balance = LeaveBalance.query.filter_by(
            user_id=leave_request.user_id,
            leave_type_id=leave_request.leave_type_id,
            calendar_year=leave_request.start_date.year,
        ).first()
        if balance:
            before = balance.available_days + leave_request.days
            output += [_paragraph("LEAVE BALANCE", styles["section"]), _information_table([
                ("Balance before approval", f"{before:.1f} days"),
                ("Leave utilized", f"{leave_request.days:.1f} days"),
                ("Remaining balance", f"{balance.available_days:.1f} days"),
            ], styles, columns=3), Spacer(1, 7 * mm)]
        output += [_paragraph("This document confirms that the above leave request has been approved in accordance with the applicable Pointlabs leave policy and approval workflow.", styles["statement"]), Spacer(1, 5 * mm), _paragraph("Pointlabs Technologies · System-generated leave confirmation", styles["note"])]
        return output

    stored_path, _ = _write_pdf(_generated_dir("leave-confirmations"), f"leave-{leave_request.id}", story)
    return stored_path, display_name
