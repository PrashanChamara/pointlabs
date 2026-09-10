#!/usr/bin/env python3
"""Generate the branded Pointlabs One user and administrator manual."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    Image,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "Pointlabs_One_User_Manual.pdf"
RING = ROOT / "app" / "static" / "images" / "pointlabs-ring.png"

PAGE_W, PAGE_H = A4
MARGIN_X = 17 * mm
TOP_MARGIN = 20 * mm
BOTTOM_MARGIN = 17 * mm
CONTENT_W = PAGE_W - (2 * MARGIN_X)

DARK = colors.HexColor("#12372C")
DARKER = colors.HexColor("#0B241D")
GREEN = colors.HexColor("#176B52")
MINT = colors.HexColor("#E9F6EF")
MINT_2 = colors.HexColor("#F5FBF7")
GOLD = colors.HexColor("#D29B2E")
GOLD_LIGHT = colors.HexColor("#FFF4D6")
ORANGE = colors.HexColor("#F06032")
INK = colors.HexColor("#14241E")
MUTED = colors.HexColor("#5E7169")
LINE = colors.HexColor("#D6E4DB")
PAPER = colors.HexColor("#FFFFFF")
BLUE = colors.HexColor("#2E67C7")
BLUE_LIGHT = colors.HexColor("#EAF1FF")
RED = colors.HexColor("#A53A3A")
RED_LIGHT = colors.HexColor("#FCECEC")


def register_fonts() -> tuple[str, str]:
    regular = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    bold = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    if regular.is_file() and bold.is_file():
        pdfmetrics.registerFont(TTFont("PLSans", str(regular)))
        pdfmetrics.registerFont(TTFont("PLSans-Bold", str(bold)))
        return "PLSans", "PLSans-Bold"
    return "Helvetica", "Helvetica-Bold"


FONT, FONT_BOLD = register_fonts()


class AccentRule(Flowable):
    def __init__(self, width: float = CONTENT_W, height: float = 7):
        super().__init__()
        self.width = width
        self.height = height

    def draw(self):
        self.canv.setFillColor(GOLD)
        self.canv.roundRect(0, self.height / 2, 27 * mm, 2.2, 1.1, fill=1, stroke=0)
        self.canv.setFillColor(ORANGE)
        self.canv.circle(29 * mm, self.height / 2 + 1.1, 1.5, fill=1, stroke=0)


class ManualDocTemplate(BaseDocTemplate):
    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name == "ChapterTitle":
            text = flowable.getPlainText()
            key = getattr(flowable, "_bookmark_name", f"chapter-{self.page}-{text}")
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level=0, closed=False)
            self.notify("TOCEntry", (0, text, self.page, key))


def draw_page(canvas, doc):
    canvas.saveState()
    if doc.page == 1:
        canvas.setFillColor(DARKER)
        canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
        canvas.setStrokeColor(colors.Color(1, 1, 1, alpha=0.08))
        canvas.setLineWidth(1)
        canvas.circle(PAGE_W - 8 * mm, PAGE_H - 25 * mm, 47 * mm, fill=0, stroke=1)
        canvas.circle(PAGE_W - 5 * mm, 14 * mm, 62 * mm, fill=0, stroke=1)
        canvas.setFillColor(GOLD)
        canvas.roundRect(MARGIN_X, 13 * mm, 38 * mm, 2.2, 1.1, fill=1, stroke=0)
        canvas.setFillColor(colors.Color(1, 1, 1, alpha=0.55))
        canvas.setFont(FONT, 7.5)
        canvas.drawRightString(PAGE_W - MARGIN_X, 13 * mm, "CONFIDENTIAL PEOPLE OPERATIONS GUIDE")
    else:
        canvas.setFillColor(MINT_2)
        canvas.rect(0, PAGE_H - 14 * mm, PAGE_W, 14 * mm, fill=1, stroke=0)
        canvas.drawImage(
            str(RING), MARGIN_X, PAGE_H - 9.5 * mm,
            width=5 * mm, height=5 * mm, mask="auto", preserveAspectRatio=True,
        )
        canvas.setFillColor(DARK)
        canvas.setFont(FONT_BOLD, 8.2)
        canvas.drawString(MARGIN_X + 7 * mm, PAGE_H - 8.2 * mm, "Pointlabs One")
        canvas.setFont(FONT, 7.2)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(PAGE_W - MARGIN_X, PAGE_H - 8.2 * mm, "USER & ADMINISTRATOR MANUAL · EDITION 1.0")
        canvas.setStrokeColor(LINE)
        canvas.line(MARGIN_X, 13 * mm, PAGE_W - MARGIN_X, 13 * mm)
        canvas.setFont(FONT, 7.2)
        canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN_X, 8.2 * mm, "Pointlabs people operations · Internal use")
        canvas.drawRightString(PAGE_W - MARGIN_X, 8.2 * mm, f"Page {doc.page}")
    canvas.restoreState()


styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="CoverBrand", fontName=FONT_BOLD, fontSize=18, leading=22, textColor=PAPER,
))
styles.add(ParagraphStyle(
    name="CoverTitle", fontName=FONT_BOLD, fontSize=31, leading=35, textColor=PAPER,
    spaceAfter=10,
))
styles.add(ParagraphStyle(
    name="CoverSub", fontName=FONT, fontSize=12, leading=18, textColor=colors.HexColor("#CFE1D7"),
))
styles.add(ParagraphStyle(
    name="CoverMeta", fontName=FONT, fontSize=8.6, leading=13, textColor=colors.HexColor("#DDEAE3"),
))
styles.add(ParagraphStyle(
    name="ChapterTitle", fontName=FONT_BOLD, fontSize=23, leading=28, textColor=INK,
    spaceBefore=2, spaceAfter=6, keepWithNext=True,
))
styles.add(ParagraphStyle(
    name="ChapterNumber", fontName=FONT_BOLD, fontSize=8, leading=10, textColor=GREEN,
    tracking=1.3, spaceAfter=4, keepWithNext=True,
))
styles.add(ParagraphStyle(
    name="Lead", fontName=FONT, fontSize=10.3, leading=15, textColor=MUTED,
    spaceAfter=10,
))
styles.add(ParagraphStyle(
    name="H2Manual", fontName=FONT_BOLD, fontSize=14.2, leading=18, textColor=INK,
    spaceBefore=11, spaceAfter=6, keepWithNext=True,
))
styles.add(ParagraphStyle(
    name="H3Manual", fontName=FONT_BOLD, fontSize=10.3, leading=13, textColor=DARK,
    spaceBefore=7, spaceAfter=3, keepWithNext=True,
))
styles.add(ParagraphStyle(
    name="BodyManual", fontName=FONT, fontSize=8.6, leading=12.4, textColor=INK,
    spaceAfter=5,
))
styles.add(ParagraphStyle(
    name="SmallManual", fontName=FONT, fontSize=7.5, leading=10.4, textColor=MUTED,
))
styles.add(ParagraphStyle(
    name="BulletManual", fontName=FONT, fontSize=8.4, leading=12, textColor=INK,
    leftIndent=11, firstLineIndent=-7, bulletIndent=2, spaceAfter=3,
))
styles.add(ParagraphStyle(
    name="StepNumber", fontName=FONT_BOLD, fontSize=10, leading=12, alignment=TA_CENTER,
    textColor=DARK,
))
styles.add(ParagraphStyle(
    name="StepTitle", fontName=FONT_BOLD, fontSize=9.2, leading=12, textColor=INK,
    spaceAfter=1,
))
styles.add(ParagraphStyle(
    name="StepText", fontName=FONT, fontSize=8.1, leading=11.4, textColor=MUTED,
))
styles.add(ParagraphStyle(
    name="CalloutTitle", fontName=FONT_BOLD, fontSize=9, leading=11.5, textColor=DARK,
    spaceAfter=2,
))
styles.add(ParagraphStyle(
    name="CalloutBody", fontName=FONT, fontSize=8.1, leading=11.5, textColor=INK,
))
styles.add(ParagraphStyle(
    name="TableHead", fontName=FONT_BOLD, fontSize=7, leading=8.5, textColor=PAPER,
))
styles.add(ParagraphStyle(
    name="TableCell", fontName=FONT, fontSize=7.2, leading=9.6, textColor=INK,
))
styles.add(ParagraphStyle(
    name="TableCellBold", fontName=FONT_BOLD, fontSize=7.2, leading=9.6, textColor=INK,
))
styles.add(ParagraphStyle(
    name="TOCTitle", fontName=FONT_BOLD, fontSize=22, leading=27, textColor=INK, spaceAfter=12,
))


def P(text: str, style: str = "BodyManual") -> Paragraph:
    return Paragraph(text, styles[style])


def section(number: str, title: str, lead: str) -> list[Flowable]:
    heading = P(title, "ChapterTitle")
    heading._bookmark_name = f"chapter-{number.replace('.', '-') }"
    return [P(f"CHAPTER {number}", "ChapterNumber"), heading, AccentRule(), Spacer(1, 4), P(lead, "Lead")]


def h2(title: str) -> Paragraph:
    return P(title, "H2Manual")


def h3(title: str) -> Paragraph:
    return P(title, "H3Manual")


def bullets(items: list[str]) -> list[Paragraph]:
    return [P(f"<font color='#D29B2E'>●</font>&nbsp;&nbsp;{item}", "BulletManual") for item in items]


def steps(items: list[tuple[str, str]]) -> Table:
    rows = []
    for index, (title, body) in enumerate(items, 1):
        number = Table([[P(str(index), "StepNumber")]], colWidths=[9 * mm], rowHeights=[9 * mm])
        number.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), GOLD_LIGHT),
            ("BOX", (0, 0), (-1, -1), 0.5, GOLD),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        rows.append([number, [P(title, "StepTitle"), P(body, "StepText")]])
    table = Table(rows, colWidths=[12 * mm, CONTENT_W - 12 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, -1), 3),
        ("RIGHTPADDING", (1, 0), (1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def callout(title: str, body: str, kind: str = "info") -> Table:
    palette = {
        "info": (MINT, GREEN),
        "warning": (GOLD_LIGHT, colors.HexColor("#8B6114")),
        "security": (BLUE_LIGHT, BLUE),
        "danger": (RED_LIGHT, RED),
    }
    background, accent = palette[kind]
    box = Table([[P(title, "CalloutTitle"), P(body, "CalloutBody")]], colWidths=[35 * mm, CONTENT_W - 35 * mm])
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), background),
        ("LINEBEFORE", (0, 0), (0, -1), 3, accent),
        ("BOX", (0, 0), (-1, -1), 0.4, accent),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return box


def data_table(headers: list[str], rows: list[list[str]], widths: list[float] | None = None) -> Table:
    if widths is None:
        widths = [CONTENT_W / len(headers)] * len(headers)
    content = [[P(item, "TableHead") for item in headers]]
    for row in rows:
        content.append([P(str(item), "TableCell") for item in row])
    table = Table(content, colWidths=widths, repeatRows=1, hAlign="LEFT")
    rules = [
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for row_index in range(1, len(content)):
        if row_index % 2 == 0:
            rules.append(("BACKGROUND", (0, row_index), (-1, row_index), MINT_2))
    table.setStyle(TableStyle(rules))
    return table


def chapter_break() -> PageBreak:
    return PageBreak()


def flatten_story(items: list[Flowable | list[Flowable]]) -> list[Flowable]:
    """Flatten helper-produced flowable groups before handing them to Platypus."""
    flattened: list[Flowable] = []
    for item in items:
        if isinstance(item, list):
            flattened.extend(flatten_story(item))
        else:
            flattened.append(item)
    return flattened


def build_story() -> list[Flowable]:
    story: list[Flowable] = []

    # Cover
    brand = Table([
        [Image(str(RING), 11 * mm, 11 * mm), P("Pointlabs <font color='#F06032'>O</font>ne", "CoverBrand")],
    ], colWidths=[14 * mm, 95 * mm], hAlign="LEFT")
    brand.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.extend([
        Spacer(1, 28 * mm), brand, Spacer(1, 39 * mm),
        P("People operations,<br/><font color='#F2C85B'>made clear.</font>", "CoverTitle"),
        P("Complete user and administrator manual", "CoverSub"),
        Spacer(1, 5 * mm),
        P("A practical guide to employee records, configurable approvals, leave, HR requests, attendance, payroll, secure documents, notifications, reports and daily administration.", "CoverSub"),
        Spacer(1, 30 * mm),
        Table([
            [P("EDITION", "CoverMeta"), P("PREPARED FOR", "CoverMeta"), P("PLATFORM", "CoverMeta")],
            [P("1.0 · 10 September 2026", "CoverMeta"), P("Pointlabs employees, managers and HR", "CoverMeta"), P("Pointlabs One HRM", "CoverMeta")],
        ], colWidths=[49 * mm, 73 * mm, 45 * mm], style=TableStyle([
            ("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.Color(1, 1, 1, alpha=0.25)),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, 0), 7),
            ("TOPPADDING", (0, 1), (-1, -1), 2),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])),
        chapter_break(),
    ])

    # Contents
    story.extend([P("Guide contents", "TOCTitle"), P("Use the PDF outline or the chapter list below to move directly to the area you need.", "Lead")])
    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle(
        name="TOCLevel0", fontName=FONT, fontSize=9, leading=17, leftIndent=0,
        firstLineIndent=0, textColor=INK, spaceBefore=2,
    )]
    story.extend([toc, Spacer(1, 7 * mm), callout(
        "Fastest way to begin",
        "New administrators should follow Chapter 4 in order, then configure access roles and workflows before employees begin submitting requests.",
        "warning",
    ), Spacer(1, 6 * mm), h2("How to use this manual")])
    story.extend(bullets([
        "Employees: focus on Chapters 2, 8, 9, 10, 11, 13 and 14.",
        "Reporting managers and workflow approvers: read Chapters 3, 7 and 8.",
        "HR and system administrators: use the full guide, especially Chapters 4 through 12 and the appendices.",
        "Screen labels are written exactly as they appear in the current Pointlabs One application wherever possible.",
    ]))
    story.append(chapter_break())

    # 1
    story.extend(section("1", "Start here", "Pointlabs One is the shared HR workspace for employee information, time, requests, approvals, payroll documents and HR operations."))
    story.extend([h2("What the system does"), P("The platform combines employee self-service with protected HR administration. Each person signs in to one responsive web application; the visible navigation and allowed actions depend on the person's account permissions and reporting relationships.")])
    story.extend(bullets([
        "Employees maintain safe profile details, check attendance, request leave, submit HR services, message colleagues, manage personal tasks and download their own documents.",
        "Reporting managers and configured approvers decide only the requests routed to them.",
        "HR manages people records, leave balances, payroll, documents, holidays, requests and reports.",
        "Configuration administrators manage organisation data, access roles, service types and approval workflows.",
    ]))
    story.extend([h2("Key terms"), data_table(
        ["TERM", "MEANING"],
        [
            ["Designation", "A person's job title, such as Software Engineer or Head of Operations. It does not automatically grant system permissions."],
            ["Access role", "An administrator-created application permission profile. It can grant HR access, configuration access, and act as an approval source."],
            ["Reporting manager", "The employee selected on a person's record as their direct reporting officer. This relationship can route approvals."],
            ["Workflow", "A reusable sequence of one or more approval stages for leave or HR requests."],
            ["Approval mode", "Any means one eligible approver can progress the stage. All means every eligible approver in that stage must approve."],
        ],
        [34 * mm, CONTENT_W - 34 * mm],
    ), Spacer(1, 5), callout("Privacy first", "Salary, bank, identity and protected document data must be handled only by authorised users. Never share downloaded records through unsecured channels.", "security")])
    story.append(chapter_break())

    # 2
    story.extend(section("2", "Sign-in, password and profile", "Start securely, recover access with a time-limited OTP, and keep the profile fields you are allowed to maintain current."))
    story.extend([h2("Signing in"), steps([
        ("Open Pointlabs One", "Use the company-provided HTTPS address. Local testers can use http://127.0.0.1:5000 after the server is started."),
        ("Enter your identity", "The login field accepts either your User ID or your registered work email address."),
        ("Enter your password", "Use the temporary password only for the first sign-in. A newly created account is required to set a personal password before continuing."),
        ("Open your workspace", "After authentication, the Overview shows only data and actions permitted for your account."),
    ]), h2("Changing a password"), P("Open the profile panel at the bottom of the navigation, select Profile & settings, then choose Change password. Enter the current password and the new personal password. After a successful change, the old temporary password no longer works.")])
    story.extend([h2("Forgotten password and OTP recovery"), steps([
        ("Choose Forgot your password?", "On the sign-in page, open the secure recovery form."),
        ("Confirm the account", "Enter the same User ID or registered email accepted at login, plus the registered email address."),
        ("Use the latest code", "A six-digit OTP is emailed to the registered address. It remains valid for 15 minutes. If a new code is requested, use the latest one."),
        ("Set a new password", "Enter the account identity, verification code and new password. Return to sign-in after the confirmation message."),
    ]), callout("OTP rejected or expired?", "Request a fresh OTP, use it within 15 minutes, and enter the same account identity used on the recovery request. Do not reuse an older code.", "warning"), h2("Profile self-service")])
    story.extend(bullets([
        "Employees can update preferred name, work email, personal email, phone and personal address.",
        "Employment, designation, manager, salary, bank and identity changes remain HR-controlled.",
        "For a protected change, submit a Personal Information Update from HR requests so the change is reviewed and recorded.",
        "Use Sign out when leaving a shared device.",
    ]))
    story.append(chapter_break())

    # 3
    story.extend(section("3", "Navigation, permissions and responsibilities", "The interface is one product, but it adapts to the signed-in person's permissions and approval responsibilities."))
    story.extend([h2("Main navigation"), data_table(
        ["AREA", "PURPOSE", "TYPICAL ACCESS"],
        [
            ["Overview", "Operational summary, current leave, notifications, birthdays and quick actions.", "All users; metrics vary by role"],
            ["My workspace", "Private tasks, reminders and sticky notes; HR can publish global notes.", "All users"],
            ["Messages", "Private colleague-to-colleague conversations.", "All active users"],
            ["People directory", "Search, filter, create, edit, archive and export employee records.", "HR / Admin"],
            ["Attendance", "Daily check-in/check-out and recent personal history.", "All users"],
            ["Leave & time off", "Balances, requests, edits, cancellations and confirmation PDFs.", "All users"],
            ["HR requests", "Certificates, letters, information updates and other services.", "All users; HR sees the service queue"],
            ["My payslips", "Secure payslip history and PDF downloads.", "Own records; HR sees authorised records"],
            ["Approvals", "Configured workflow decisions and manager/HR queues.", "Eligible approvers"],
            ["Reports", "Leave, employee and attendance reporting/export.", "HR / Admin"],
            ["Admin centre / Workflow studio", "People operations and configuration.", "Authorised HR / configuration users"],
        ], [38 * mm, 82 * mm, CONTENT_W - 120 * mm]
    )])
    story.extend([h2("Who can do what"), data_table(
        ["RESPONSIBILITY", "EMPLOYEE", "APPROVER / MANAGER", "HR / ADMIN"],
        [
            ["Own profile, attendance, leave, HR requests", "Create and maintain eligible own records", "Same self-service rights", "Same self-service rights"],
            ["Approve requests", "Only if explicitly routed", "Decisions assigned by workflow or reporting line", "Decisions assigned by workflow plus HR service processing"],
            ["Employee records and confidential data", "No", "No, unless separately granted", "Authorised access"],
            ["Configuration", "No", "Only with configuration access role", "Administrator or configured role"],
        ], [46 * mm, 41 * mm, 48 * mm, CONTENT_W - 135 * mm]
    ), Spacer(1, 5), callout("Designations are not permissions", "A senior job title does not automatically create HR access. Assign a separate access role when a person needs application permissions or workflow responsibility.", "warning")])
    story.append(chapter_break())

    # 4
    story.extend(section("4", "Initial organisation setup", "Configure reusable organisation data before onboarding the wider team. This order prevents incomplete profiles and unroutable approvals."))
    story.extend([h2("Recommended setup sequence"), steps([
        ("Entities / companies", "Create the employing companies. Record display name, legal name, two-letter country code and three-letter currency."),
        ("Locations", "Create offices or work locations and connect each one to an entity. Add the country code used for holiday and payslip selection."),
        ("Departments", "Create reusable departments for employee records, reporting and filters."),
        ("Designations", "Create job titles and mark only titles eligible to be selected as reporting officers."),
        ("Access roles", "Create the application permission profiles required for HR, configuration and workflow routing."),
        ("Approval workflows", "Create leave and HR service routes, add their stages, verify eligible approvers, then activate them."),
        ("Employees", "Create accounts and profiles, then assign entity, location, department, designation, reporting manager and access role."),
        ("Leave and payroll configuration", "Set holiday calendars, opening leave adjustments and effective-dated compensation."),
    ])])
    story.extend([h2("Master data rules"), bullets([
        "Use stable, recognisable names; avoid duplicates such as Dubai and DXB Office unless they are genuinely separate records.",
        "Use country code LK for Sri Lanka and AE for the United Arab Emirates where applicable.",
        "Use LKR and AED as currency codes. These values help select the appropriate payslip context.",
        "Archive or deactivate referenced records rather than deleting history.",
    ]), h2("Where to configure")])
    story.append(data_table(
        ["CONFIGURATION", "ENTRY POINT"],
        [
            ["Entities, locations, departments", "Admin centre → organisation/master data links"],
            ["Designations", "Admin centre → Designations"],
            ["Access roles", "Workflow studio / administration → Access roles"],
            ["Approval routes and HR request types", "Workflow studio → Approval workflows"],
            ["Public holidays", "Admin centre → Public holiday calendar"],
            ["Leave balance adjustments", "Admin centre → Leave balances"],
        ], [60 * mm, CONTENT_W - 60 * mm]
    ))
    story.append(chapter_break())

    # 5
    story.extend(section("5", "Employee management", "Maintain a complete employee lifecycle without deleting historical HR, leave, payroll or document records."))
    story.extend([h2("Finding people"), P("Open People directory. Search by name, employee code or email; combine search with department, location and employment-status filters. The list uses stable pagination with 10 people per page by default. Use Export CSV only when you are authorised to handle the resulting data.")])
    story.extend([h2("Creating an employee"), steps([
        ("Open Add employee", "From People directory, choose Add employee."),
        ("Create the account", "Enter full name, unique User ID, temporary password, work email and employee code. A temporary employee code is acceptable when the permanent ID is unavailable."),
        ("Assign employment data", "Set status, dates, employment type, entity, location, department, designation and reporting manager."),
        ("Assign system access", "Leave Standard employee access for most users. Select an administrator-created access role only when required."),
        ("Complete personal, identity and banking data", "Enter verified information. Sensitive fields are protected from normal employee editing."),
        ("Attach initial documents", "Optionally upload multiple PDFs or supported images and provide a document category."),
        ("Create and hand over", "Save the account and give the temporary credentials through a secure channel. The user must change the password at first login."),
    ])])
    story.extend([h2("Editing and employee lifecycle"), bullets([
        "Use Edit employee from the employee detail page for HR-controlled corrections.",
        "Do not assign a person as their own reporting manager. Keep reporting lines current so approvals route correctly.",
        "Set a resignation date rather than deleting the person. On the effective date, login is disabled while history remains.",
        "Archive access only when business rules permit. The current administrator cannot archive their own account from the employee page.",
        "Employee detail links directly to leave balances, salary and payslips, and secure document history.",
    ]), callout("Before saving", "Verify work email, entity/location, designation, reporting manager and access role. These fields directly influence notifications, leave calendars, payroll templates and approval routing.", "info")])
    story.append(chapter_break())

    # 6
    story.extend(section("6", "Designations and access roles", "Keep job identity separate from application authority. This is the foundation of safe and flexible workflow design."))
    story.extend([h2("Managing designations"), steps([
        ("Open Designations", "From Admin centre, open the designation catalogue."),
        ("Add a job title", "Enter the exact job title used by Pointlabs."),
        ("Set reporting eligibility", "Tick This designation can be a reporting officer only when holders of that title may be selected as reporting managers."),
        ("Maintain the catalogue", "Use the row action to change reporting-officer eligibility when organisation responsibilities change."),
    ]), h2("Creating an access role"), steps([
        ("Open Access roles", "Use the administration/configuration navigation."),
        ("Name and describe the role", "Examples include People Operations or Payroll Administrator. Describe the business access it provides."),
        ("Choose privileges", "Grant HR operational access to users who manage protected HR work. Grant configuration access only to users who manage master data and workflows."),
        ("Save and assign", "Create the role, then assign it on the employee's Edit employee screen."),
        ("Archive safely", "Archive an obsolete role rather than deleting it. Existing assignments and historical approvals remain traceable."),
    ])])
    story.extend([callout("Least privilege", "Give each person only the access needed for their current responsibilities. Review access after promotions, transfers, leave cover and resignations.", "security"), h2("A practical separation")])
    story.append(data_table(
        ["PERSON", "DESIGNATION", "ACCESS ROLE", "REPORTING MANAGER"],
        [
            ["Software engineer", "Senior Software Engineer", "Standard employee", "Head of Engineering"],
            ["HR specialist", "People Operations Executive", "People Operations (HR access)", "Head of Operations"],
            ["Workflow approver", "Finance Manager", "Finance Approval", "Chief Finance Officer"],
        ], [39 * mm, 46 * mm, 51 * mm, CONTENT_W - 136 * mm]
    ))
    story.append(chapter_break())

    # 7
    story.extend(section("7", "Workflow Studio: create approval routes", "Build administrator-managed, sequential approval routes without hard-coding employee names, roles or job titles into the application."))
    story.extend([h2("Create a workflow"), steps([
        ("Open Workflow studio", "The link appears for the system administrator and access roles allowed to manage configuration."),
        ("Create a route", "Enter a unique workflow name, choose Leave requests or HR service requests, add a clear description, and create the workflow."),
        ("Add the first stage", "Choose the stage rule and approver source. Complete the corresponding designation, access role or named employee field where required."),
        ("Add later stages", "Use Add next stage. Each new stage is placed after the previous one; the system activates them sequentially."),
        ("Validate approver availability", "Confirm that every stage resolves to at least one active eligible person for likely requesters."),
        ("Activate", "A route cannot be activated without a stage. Activate only after the full path has been checked."),
    ])])
    story.extend([h2("Approver sources"), data_table(
        ["SOURCE", "HOW IT RESOLVES", "BEST USE"],
        [
            ["Designation", "All active employees currently holding the selected designation.", "Department or leadership approvals independent of named individuals"],
            ["Access role", "All active users assigned the selected application role.", "Finance, HR or specialist approval groups"],
            ["Direct manager", "The requester's assigned reporting manager.", "First-line leave or operational approval"],
            ["Any HR administrator", "All active users with HR operational access.", "HR review queue"],
            ["Named employee", "One specifically selected active person.", "A stable, exceptional approval responsibility"],
        ], [34 * mm, 71 * mm, CONTENT_W - 105 * mm]
    ), h2("Stage rules: Any versus All"), data_table(
        ["RULE", "RESULT"],
        [
            ["Any one approver", "The first eligible approval completes that stage; other pending decisions in the same stage are skipped."],
            ["All eligible approvers", "Every eligible person in the stage must approve before the workflow proceeds."],
        ], [43 * mm, CONTENT_W - 43 * mm]
    )])
    story.append(chapter_break())

    # 7 examples continuation
    story.extend([P("WORKFLOW EXAMPLES", "ChapterNumber"), P("Three reliable patterns", "ChapterTitle"), AccentRule(), Spacer(1, 4), P("Choose the simplest route that satisfies the real decision process. Complexity adds waiting time and maintenance.", "Lead")])
    story.extend([h2("Example A: direct manager only"), data_table(
        ["STAGE", "MODE", "SOURCE", "OUTCOME"],
        [["1", "Any", "Direct manager", "The employee's assigned manager can approve, reject or ask for more information."]],
        [17 * mm, 25 * mm, 44 * mm, CONTENT_W - 86 * mm]
    ), h2("Example B: manager, then HR"), data_table(
        ["STAGE", "MODE", "SOURCE", "OUTCOME"],
        [
            ["1", "Any", "Direct manager", "Manager reviews operational coverage."],
            ["2", "Any", "Any HR administrator", "HR completes policy and record review."],
        ], [17 * mm, 25 * mm, 44 * mm, CONTENT_W - 86 * mm]
    ), h2("Example C: parallel finance approval, then HR"), data_table(
        ["STAGE", "MODE", "SOURCE", "OUTCOME"],
        [
            ["1", "All", "Finance Approval access role", "Every active person in the finance approval group must approve."],
            ["2", "Any", "Any HR administrator", "Any eligible HR user can complete the final approval stage."],
        ], [17 * mm, 25 * mm, 48 * mm, CONTENT_W - 90 * mm]
    )])
    story.extend([h2("Decision outcomes"), bullets([
        "Approve progresses the current stage. If it is the last required decision, the business request moves to its approved state.",
        "Reject ends the approval instance and records the approver's comment.",
        "More information required returns the request to the creator. The creator edits or responds, then the same recorded stage becomes active again.",
        "Every decision is tied to its approver, stage and timestamp. In-flight requests preserve their original workflow history.",
    ]), callout("Route selection rule", "Keep one general leave workflow active. For HR services, keep one general route active and assign service-specific routes directly to request types when needed. This prevents competing active routes from creating an unexpected path.", "warning"), Spacer(1, 5), callout("No eligible approvers", "A request cannot start when a required stage resolves to no active person. Check the employee's reporting manager, assigned designations, access-role membership and active account status before activating the route.", "danger")])
    story.append(chapter_break())

    # 8
    story.extend(section("8", "Leave and time off", "Employees can see balances, submit and correct leave, receive multi-stage decisions, cancel requests safely and retain official confirmation documents."))
    story.extend([h2("Before employees submit leave"), bullets([
        "HR assigns correct entity/location so the right public holidays are excluded.",
        "HR verifies the date of joining, probation end date, resignation/notice status and reporting manager.",
        "HR reviews the employee's yearly balances and records any authorised opening or correction adjustment.",
        "Configuration administrators activate a valid leave workflow, or HR ensures the reporting-manager fallback is correct.",
    ]), h2("Submit leave"), steps([
        ("Open Leave & time off", "Review the displayed annual, sick and other available balances."),
        ("Choose leave type and dates", "The system calculates working days after excluding weekends and applicable public holidays."),
        ("Add context", "Enter a handover or reason that helps the approver make a decision."),
        ("Submit", "The request appears in history and the first configured approver receives an in-app notification."),
    ])])
    story.extend([h2("Rules applied by the current system"), bullets([
        "Annual leave is unavailable before the recorded probation end date.",
        "Leave is blocked during a recorded notice period.",
        "A period with no working days cannot be submitted.",
        "When a non-LWP request exceeds the available balance and Leave Without Pay is active, it is recorded as LWP for review.",
        "Approved leave reduces the relevant balance only once.",
    ]), h2("Edit, return, reject and cancel")])
    story.append(data_table(
        ["CURRENT STATE", "EMPLOYEE ACTION", "APPROVER / HR ACTION"],
        [
            ["Submitted or returned", "Edit dates/type/reason, or cancel the pending request.", "Approve, reject, or request more information."],
            ["Approved", "Request cancellation and provide a reason.", "Approve or decline cancellation."],
            ["Cancellation requested", "Wait for the decision.", "Approval restores the applicable balance; decline keeps leave approved."],
            ["Rejected / cancelled", "View history; no further editing.", "History remains available."],
        ], [42 * mm, 65 * mm, CONTENT_W - 107 * mm]
    ))
    story.extend([h2("Leave Confirmation PDF"), P("A final approval generates one official Pointlabs Leave Confirmation PDF with employee, leave, approver, dates, duration and reference details. The employee, authorised HR and the reporting manager can download it. If the approved leave is later cancelled, the original document remains for audit history.")])
    story.append(chapter_break())

    # 9
    story.extend(section("9", "HR service requests", "Use the service desk for certificates, letters, document copies, personal information changes and administrator-defined HR services."))
    story.extend([h2("Create and follow a request"), steps([
        ("Open HR requests", "Employees may see the label Other requests; HR sees the shared HR requests queue."),
        ("Select a request type", "The list is managed in Workflow Studio. Choose the service that best matches the need."),
        ("Add subject and details", "Include relevant dates, recipient requirements and context. Do not place passwords or unnecessary identity data in free text."),
        ("Submit", "If the service type has a workflow, it enters that route. Otherwise HR receives the service notification."),
        ("Open the request detail", "Track status, read public activity, add comments, edit eligible fields and respond to information requests."),
    ])])
    story.extend([h2("Employee controls"), bullets([
        "The creator can edit a Draft, Submitted, More Information Required or Resubmitted request.",
        "A request needing more information can be updated and resubmitted into the recorded approval stage.",
        "The creator can cancel a non-final request. Cancellation preserves history instead of deleting the record.",
        "Completed, cancelled and rejected requests are read-only to the employee.",
    ]), h2("HR processing")])
    story.append(data_table(
        ["STATUS", "WHEN TO USE"],
        [
            ["In review", "HR has opened the request and is checking requirements."],
            ["More information required", "The employee must provide missing or corrected information."],
            ["In progress", "HR is actively preparing or coordinating the service."],
            ["Completed", "The requested service or final document has been delivered."],
            ["Rejected", "The request cannot be fulfilled; a clear employee-facing reason should be recorded."],
        ], [43 * mm, CONTENT_W - 43 * mm]
    ))
    story.extend([P("HR can add a public comment that the employee sees, or an Internal HR note visible only to authorised HR users. When a status changes, the employee receives an in-app notification and, where configured, a branded email.")])
    story.append(chapter_break())

    # 10
    story.extend(section("10", "Attendance", "Record the current workday in a simple personal timeline and export an authorised attendance register for HR."))
    story.extend([h2("Daily employee use"), steps([
        ("Open Attendance", "The Today card shows whether the current workday is not started, open or complete."),
        ("Check in", "Add an optional note such as office, remote work or client visit, then choose Check in now."),
        ("Check out", "At the end of the workday, add an optional handover note and choose Check out."),
        ("Review history", "The recent history lists up to the last 20 workdays and distinguishes open from completed days."),
    ])])
    story.extend([h2("HR attendance export"), P("Authorised HR users can export the attendance register from the administration/reporting area. Store exported files securely because they contain employee working-time information."), callout("Time display", "The current attendance screen identifies its recorded time as UTC. Operational teams should agree how UTC records are interpreted for local working hours.", "info")])
    story.append(chapter_break())

    # 11
    story.extend(section("11", "Payroll, compensation and payslips", "Record effective-dated compensation, generate versioned monthly payslip PDFs and deliver them securely."))
    story.extend([h2("Record compensation"), steps([
        ("Open Admin centre → Payroll & compensation", "Filter or select the employee whose salary record must be maintained."),
        ("Choose an effective date", "Each revision becomes part of the compensation history; do not overwrite past payroll facts."),
        ("Enter salary components", "Record currency, basic salary, allowances, other earnings and the applicable deductions."),
        ("Review calculated totals", "Gross salary, total deductions and net salary are derived from the recorded components."),
        ("Save the revision", "The dated record becomes the applicable source for payroll periods on or after its effective date until a later revision applies."),
    ])])
    story.extend([h2("Generate a monthly payslip"), steps([
        ("Select payroll year and month", "The payroll screen lists eligible employees and the compensation record applicable to that period."),
        ("Review before generation", "Check employee entity/location, currency and every earning/deduction input."),
        ("Generate PDF", "The server creates a private, branded A4 PDF and stores a random internal filename. Generation must succeed before the record is marked Generated."),
        ("Deliver", "The employee receives an in-app notification. If SMTP is configured and the employee has an email, the branded email includes the confidential PDF attachment."),
        ("Correct through a new version", "Generating the same month again creates the next version. Older versions remain in history for auditability."),
    ])])
    story.extend([h2("Sri Lanka and UAE templates"), data_table(
        ["CONTEXT", "SELECTION", "KEY COMPONENTS"],
        [
            ["Sri Lanka", "Employee entity/location country is not AE", "Pointlabs Technologies Pvt Ltd · LKR · Basic, allowances, other earnings, WHT, EPF, PAYE, other deductions"],
            ["UAE / Dubai", "Employee entity or location country is AE", "Pointlabs Technologies Ltd · AED · Basic, allowances, other earnings and other deductions"],
        ], [32 * mm, 54 * mm, CONTENT_W - 86 * mm]
    ), callout("Confidential delivery", "Employees can download only their own payslips. HR/Admin access is server-authorised. Never send a payslip to an unverified or personal address without approved company procedure.", "security")])
    story.append(chapter_break())

    # 12
    story.extend(section("12", "Documents and compliance", "Store employee PDFs and images privately, link them to the right employee, and monitor critical identity-document expiry dates."))
    story.extend([h2("Upload employee documents"), steps([
        ("Open Documents", "Administrators can select the target employee; an employee sees only their own library."),
        ("Choose a category", "Use a clear label such as Passport, Emirates ID, visa, qualification or employment contract."),
        ("Choose the file", "Supported images and PDF files are accepted. Images are optimised and stored as WebP; PDFs retain their original format."),
        ("Upload", "The record is associated with the employee profile and becomes available only through authenticated, permission-checked download routes."),
    ])])
    story.extend([h2("Upload during onboarding"), P("The Add/Edit employee form also supports multiple documents. Provide a document category and choose the relevant files before saving the employee.")])
    story.extend([h2("Compliance reminders"), P("Passport and Emirates ID expiry dates in the employee record are monitored by the scheduled compliance process. It creates once-only reminders at configured thresholds for the employee and authorised HR users."), callout("Storage rule", "Do not place employee documents, generated payslips or leave confirmations in public static folders. Use only the application's secured upload and download flows.", "security")])
    story.append(chapter_break())

    # 13
    story.extend(section("13", "Messages, notifications, email and birthdays", "Keep operational communication attached to the right user and event while preserving a clear in-app record."))
    story.extend([h2("Direct messages"), steps([
        ("Open Messages", "The conversation list shows active colleagues."),
        ("Choose a colleague", "Open the existing thread or start a new one."),
        ("Write and send", "Messages are private to the sender and recipient. Use HR requests—not chat—for formal service or record changes."),
    ])])
    story.extend([h2("In-app notifications"), bullets([
        "Notifications are created for leave submissions and decisions, workflow actions, HR request updates, payslip availability, task reminders, birthdays and document-expiry reminders.",
        "The Overview and inbox areas surface unread or priority activity.",
        "A business transaction remains recorded even when email is temporarily unavailable; email failure must not be mistaken for process failure.",
    ]), h2("Branded email")])
    story.append(P("Where SMTP is configured, Pointlabs-branded emails support password OTPs, workflow notices, leave decisions, direct-message alerts, birthdays and payslip/leave document delivery. PDF attachments are confidential and must go only to the employee address associated with the record."))
    story.extend([h2("Birthday operations"), P("The birthday screen shows celebrations occurring in the next three days. The scheduled process notifies administrators three days before and sends the birthday email on the birthday when the employee has a work email. Voucher details can be associated where configured.")])
    story.append(chapter_break())

    # 14
    story.extend(section("14", "My workspace: tasks and sticky notes", "Create a lightweight personal work system inside Pointlabs One without mixing informal reminders into formal HR records."))
    story.extend([h2("To-do list"), steps([
        ("Add a task", "Enter a short action title and, optionally, a due date and time."),
        ("Complete or reopen", "Use the check control to toggle completion."),
        ("Delete", "Remove a personal task when it is no longer useful. Formal HR tasks should remain in their proper workflow instead."),
        ("Receive a reminder", "When the scheduled reminder process runs, a due incomplete task creates a once-only in-app reminder."),
    ])])
    story.extend([h2("Sticky notes"), bullets([
        "Create a short note and choose gold, green or rose.",
        "Select Show on my screens to keep a personal note visible across the application.",
        "Authorised HR users can select Show on every employee workspace for a company-wide note.",
        "Remove notes when they are no longer current. Global notes should be concise and time-sensitive.",
    ]), callout("Use the right channel", "Tasks and notes are reminders, not approval evidence. Keep leave, employee changes, HR services and payroll actions in their formal modules so history remains auditable.", "info")])
    story.append(chapter_break())

    # 15
    story.extend(section("15", "Reports and exports", "Use protected operational reporting for decisions, reconciliations and controlled offline analysis."))
    story.extend([h2("Reports available"), data_table(
        ["REPORT", "USE", "OUTPUT"],
        [
            ["Reports dashboard", "Active employees, leave awaiting decision, approved leave and period activity.", "On-screen"],
            ["Leave Summary", "Entitled, accrued, utilised and available annual/sick balances for a selected year/period.", "CSV"],
            ["Leave activity", "Request dates, working days, type, status and available confirmation document.", "On-screen / CSV"],
            ["Full employee detail", "Protected employee information for authorised HR analysis.", "CSV"],
            ["Attendance register", "Employee check-in and check-out records.", "CSV"],
        ], [39 * mm, 84 * mm, CONTENT_W - 123 * mm]
    )])
    story.extend([h2("Run a leave-period review"), steps([
        ("Open Reports", "The page is available only to authorised HR users."),
        ("Set From date and To date", "Choose the exact reporting period and apply it."),
        ("Review metrics and rows", "Check totals, leave status, duration and confirmation-document availability."),
        ("Export the correct dataset", "Use Leave summary CSV for balance analysis or the leave activity export for request-level analysis."),
        ("Protect the export", "Store it in an approved location and delete local copies when no longer required."),
    ]), callout("Balance interpretation", "Entitlement, accrual, utilised leave, adjustments and available balance are separate values. Do not treat a sum of request rows as the employee's authoritative remaining balance.", "warning")])
    story.append(chapter_break())

    # 16
    story.extend(section("16", "Operating checklists", "Use these short routines to keep the HR workspace accurate and prevent pending work from becoming invisible."))
    story.extend([h2("Employee: daily or as needed")])
    story.extend(bullets([
        "Check Overview for personal notifications and returned requests.",
        "Check in and out from Attendance according to company practice.",
        "Keep contact details current and use HR requests for protected changes.",
        "Respond promptly when an approver or HR requests more information.",
        "Download payslips and leave confirmations only to a trusted device.",
    ]))
    story.extend([h2("Approver / reporting manager: daily")])
    story.extend(bullets([
        "Open Approvals and review only decisions assigned to you.",
        "Check dates, working days, handover context and team coverage before a leave decision.",
        "Use More information required when facts are missing; explain exactly what is needed.",
        "Add a clear reason when rejecting or declining a cancellation.",
    ]))
    story.extend([h2("HR: weekly")])
    story.extend(bullets([
        "Review pending leave, cancellation and HR service queues.",
        "Check new starters, future resignations, document expiry and missing reporting managers.",
        "Reconcile leave-balance adjustments against approved references.",
        "Confirm public holidays for each active entity/location.",
        "Review access assignments and archived accounts.",
    ]))
    story.extend([h2("HR / payroll: monthly")])
    story.extend(bullets([
        "Confirm current compensation revisions before selecting the payroll period.",
        "Validate currency and Sri Lanka/UAE template selection for each employee.",
        "Generate, inspect and deliver payslip PDFs; correct errors through a new version.",
        "Export required reports, reconcile totals and protect downloaded data.",
    ]))
    story.append(chapter_break())

    # 17
    story.extend(section("17", "Mobile use, theme and installation", "Pointlabs One is responsive and installable as a Progressive Web App, while retaining the same permission controls as the desktop experience."))
    story.extend([h2("Mobile navigation"), bullets([
        "Use the menu button to open the navigation drawer. Choose a destination or use the visible close button; tapping the page backdrop also closes the drawer.",
        "Tables may scroll horizontally or adapt into smaller layouts. Use landscape orientation when reviewing wide HR data.",
        "Keep the device locked and sign out before lending it to another person.",
    ]), h2("Light and dark theme"), P("Use the theme control in the top bar to switch between the light green/white workspace and the dark Pointlabs theme. The preference is retained by the browser.")])
    story.extend([h2("Install as an app"), steps([
        ("Open the secure production site", "PWA installation should be performed from the HTTPS deployment, not an untrusted copy."),
        ("Use the browser install action", "In Chrome/Edge, choose Install when offered or use the browser menu's Install app option. On supported mobile browsers, use Add to Home Screen."),
        ("Launch from the app icon", "The installed app opens Pointlabs One in its own window and still requires authentication."),
        ("Refresh after an update", "If a newly released interface looks mixed or outdated, close all app windows and reload once so the new service-worker cache takes effect."),
    ])])
    story.append(chapter_break())

    # 18
    story.extend(section("18", "Troubleshooting", "Resolve common user and configuration issues without bypassing security or damaging business history."))
    story.append(data_table(
        ["SYMPTOM", "CHECK", "SAFE ACTION"],
        [
            ["Valid email cannot sign in", "Confirm it is the registered work email and the account is active.", "Try the unique User ID; ask HR to verify the account email and status."],
            ["OTP says invalid or expired", "Code age, latest code, and account identity.", "Request a new OTP and use it within 15 minutes."],
            ["No approver receives a request", "Active workflow, stage source, employee manager and active eligible users.", "Correct configuration before resubmitting; do not approve directly in the database."],
            ["Leave has zero working days", "Weekend and applicable holiday calendar.", "Choose dates containing working days or correct the holiday scope."],
            ["Leave changed to LWP", "Available balance compared with requested working days.", "Ask HR to verify balance/adjustments before approval."],
            ["Payslip cannot be generated", "Applicable compensation record, payroll period and employee country/currency.", "Correct the source data and generate a new version. Do not claim delivery when PDF generation failed."],
            ["Email not received", "Registered email, spam folder and SMTP status.", "Use the in-app record; HR can resend an existing payslip PDF when available."],
            ["Old or broken interface after release", "Browser/PWA cache.", "Hard refresh, close installed app windows, or clear only the site's cached data."],
            ["Forbidden response", "Signed-in identity and required permission.", "Return to your permitted workspace; ask an administrator to review access rather than sharing credentials."],
        ], [42 * mm, 62 * mm, CONTENT_W - 104 * mm]
    ))
    story.extend([Spacer(1, 6), callout("When escalating an issue", "Record the time, user ID, page, action, displayed message and relevant business reference. Do not include passwords, OTPs, full bank data or identity numbers in screenshots or support messages.", "security")])
    story.append(chapter_break())

    # 19
    story.extend(section("19", "Security and data-handling guide", "Pointlabs One contains confidential employment, payroll, banking, identity and leave information. Good operational habits are part of the control system."))
    story.extend([h2("Required practices")])
    story.extend(bullets([
        "Use a unique personal password and never share your login, password or OTP.",
        "Grant HR and configuration access through administrator-created access roles using least privilege.",
        "Verify the selected employee before uploading a document, changing a balance or generating a payslip.",
        "Download sensitive exports and PDFs only when needed and store them in approved encrypted locations.",
        "Never send payslips, bank details or identity documents through public links or unapproved messaging channels.",
        "Use archive, resignation and cancellation workflows instead of deleting historical records.",
        "Review audit history after sensitive corrections or unexpected workflow outcomes.",
        "Keep production debug mode disabled and store SMTP/database/secret values only in protected environment configuration.",
    ]))
    story.extend([h2("Access boundaries enforced by the system"), data_table(
        ["DATA / ACTION", "BOUNDARY"],
        [
            ["Payslip PDF", "Employee owner or authorised HR/Admin only"],
            ["Leave Confirmation PDF", "Employee owner, reporting manager or authorised HR/Admin only"],
            ["Employee document", "Employee owner or authorised administrator according to the document route"],
            ["HR request", "Creator and authorised HR; internal HR notes remain hidden from employees"],
            ["Workflow decision", "Only the specifically assigned active approver can act"],
            ["Salary, bank and identity fields", "HR-controlled; employee uses an audited update request"],
        ], [55 * mm, CONTENT_W - 55 * mm]
    )])
    story.append(chapter_break())

    # 20
    story.extend(section("20", "Status reference and quick actions", "Use consistent status language to understand where work is and what action is permitted next."))
    story.extend([h2("Leave statuses"), data_table(
        ["STATUS", "MEANING", "NEXT ACTION"],
        [
            ["Submitted", "Waiting for the current approver.", "Employee may edit/cancel; approver decides."],
            ["Returned", "More information is required.", "Employee updates and resubmits."],
            ["Approved", "Final approval completed and balance applied.", "Download confirmation or request cancellation."],
            ["Rejected", "The request was declined.", "Review comment; create a new request if appropriate."],
            ["Cancellation requested", "An approved leave cancellation awaits review.", "Manager/HR approves or declines."],
            ["Cancelled", "The leave is no longer active.", "History and any original confirmation remain."],
        ], [35 * mm, 72 * mm, CONTENT_W - 107 * mm]
    ), h2("HR request statuses"), data_table(
        ["STATUS", "MEANING"],
        [
            ["Submitted", "Received and awaiting approval or HR review."],
            ["More information required", "Employee response is required."],
            ["Resubmitted", "Employee supplied an update after HR feedback."],
            ["In review", "HR is evaluating the request."],
            ["In progress", "The service is actively being prepared."],
            ["Completed", "The service is finished and final history is retained."],
            ["Cancelled / Rejected", "Closed without completion; the audit trail remains."],
        ], [49 * mm, CONTENT_W - 49 * mm]
    )])
    story.append(chapter_break())

    # Appendix A
    story.extend(section("A", "Administrator launch checklist", "Complete this checklist before inviting the wider team or enabling automated email delivery."))
    checklist = [
        "Production database configured and migrations applied without resetting existing data.",
        "Unique production SECRET_KEY set; debug mode disabled.",
        "HTTPS deployment and secure session environment confirmed.",
        "Entities, locations, country codes and currencies verified.",
        "Departments and designations reviewed; reporting-officer eligibility set.",
        "Access roles created and assigned using least privilege.",
        "Leave and HR service workflows contain eligible approvers and are active.",
        "HR request service catalogue reviewed.",
        "Employees have verified email, entity/location, designation and manager.",
        "Opening leave balances and public holidays recorded.",
        "Compensation records verified before first payroll run.",
        "SMTP tested with a controlled internal address; no real employee test blast performed.",
        "Birthday, task-reminder and compliance scheduler jobs configured.",
        "Payslip and Leave Confirmation PDFs generated and access-tested.",
        "Backup, restore, log monitoring and authorised support ownership confirmed.",
    ]
    rows = []
    for item in checklist:
        rows.append([P("□", "TableCellBold"), P(item, "TableCell")])
    checklist_table = Table(rows, colWidths=[10 * mm, CONTENT_W - 10 * mm])
    checklist_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("BACKGROUND", (0, 0), (0, -1), MINT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(checklist_table)
    story.append(chapter_break())

    # Appendix B
    story.extend(section("B", "System-owner operations", "Technical commands for the authorised maintainer. Run them from the project root using the configured virtual environment and production environment variables."))
    story.extend([h2("Local start")])
    story.append(callout("Development command", "Activate the project virtual environment, then run: python run.py. The default local address is http://127.0.0.1:5000. The development database is SQLite unless DATABASE_URL overrides it.", "info"))
    story.extend([h2("Database setup and migration"), data_table(
        ["TASK", "COMMAND"],
        [
            ["Apply existing migrations", "flask --app run:app db upgrade"],
            ["Initial local tables only", "flask --app run:app init-db"],
            ["Seed local reference data", "flask --app run:app seed-demo"],
        ], [57 * mm, CONTENT_W - 57 * mm]
    ), P("Do not run demo seeding or destructive database commands against production data unless the deployment procedure explicitly requires and protects that action.")])
    story.extend([h2("Scheduled processes"), data_table(
        ["PROCESS", "COMMAND", "SUGGESTED SCHEDULE"],
        [
            ["Birthday reminders/email", "flask --app run:app process-birthdays", "Daily"],
            ["Due task reminders", "flask --app run:app process-reminders", "Every few minutes"],
            ["Passport / Emirates ID expiry", "flask --app run:app process-compliance", "Daily"],
        ], [43 * mm, 76 * mm, CONTENT_W - 119 * mm]
    )])
    story.extend([h2("Environment configuration"), bullets([
        "DATABASE_URL: production database connection.",
        "SECRET_KEY: long, random production-only secret.",
        "SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD and SMTP_FROM: branded email delivery.",
        "FLASK_CONFIG=production: enables the production configuration, including CSRF protection.",
    ]), callout("Secret handling", "Never place real passwords, SMTP app passwords, database credentials or production secret keys in this manual, source control, screenshots or support tickets.", "security")])
    story.append(chapter_break())

    # Final
    story.extend([P("READY REFERENCE", "ChapterNumber"), P("Pointlabs One at a glance", "ChapterTitle"), AccentRule(), Spacer(1, 4), P("A secure process is a complete process: correct data, correct approver, recorded decision, protected document and clear notification.", "Lead")])
    story.append(data_table(
        ["I NEED TO…", "GO TO…"],
        [
            ["Update my phone or address", "Profile & settings"],
            ["Request leave or cancel approved leave", "Leave & time off"],
            ["Request a certificate or data update", "HR requests"],
            ["Respond to an approver", "Open the returned leave or HR request"],
            ["Approve assigned work", "Approvals"],
            ["Add or edit an employee", "People directory"],
            ["Correct a leave balance", "Admin centre → Leave balances"],
            ["Add a country holiday", "Admin centre → Public holiday calendar"],
            ["Record salary or generate a payslip", "Admin centre → Payroll & compensation"],
            ["Create a multi-stage route", "Workflow studio → Approval workflows"],
            ["Create HR/configuration permissions", "Access roles"],
            ["Export leave or employee data", "Reports"],
        ], [67 * mm, CONTENT_W - 67 * mm]
    ))
    story.extend([Spacer(1, 10 * mm), callout("Document control", f"Edition 1.0 generated {date(2026, 9, 10).strftime('%d %B %Y')}. Update and regenerate this manual whenever navigation, permissions, business statuses or workflow behaviour changes.", "info")])
    return story


def generate() -> Path:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    document = ManualDocTemplate(
        str(OUTPUT), pagesize=A4,
        leftMargin=MARGIN_X, rightMargin=MARGIN_X,
        topMargin=TOP_MARGIN, bottomMargin=BOTTOM_MARGIN,
        title="Pointlabs One User and Administrator Manual",
        author="Pointlabs",
        subject="Complete operating guide for Pointlabs One HRM",
        creator="Pointlabs One documentation generator",
    )
    frame = Frame(
        MARGIN_X, BOTTOM_MARGIN, CONTENT_W, PAGE_H - TOP_MARGIN - BOTTOM_MARGIN,
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
    )
    document.addPageTemplates([PageTemplate(id="Manual", frames=[frame], onPage=draw_page)])
    document.multiBuild(flatten_story(build_story()))
    return OUTPUT


if __name__ == "__main__":
    result = generate()
    print(result)
