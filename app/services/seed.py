from app.extensions import db
from app.models.organization import Designation
from app.models.user import EmployeeProfile, User
from app.models.hr import LeaveType, RequestType

DESIGNATIONS = """Chief Business Officer|Chief Executive Officer|Chief Finance & Compliance Officer|Chief Technology & Innovation Officer|Consultant - Partnership|Consultant UI UX Designer|Consultant – IT Program Manager|Country Head South Asia|Finance Manager|Frontend Developer|Gen AI Engineer|Head of Engineering|Head of Operations|Head of Product|Head – Global Partnerships & Alliances|Intern Product Management|Lead Back-End Engineer|Manager Quality Assurance|Manager, Partnerships & Operations|Marketing Support|Merchant Partnership Manager|Principal Engineering Consultant|Principal Quality Assurance Consultant|Principal Software Developer|Product Designer|Quality Assurance Consultant|Senior Developer|Snr Partnership Manager|Solution Architect|Sr Front-End Developer|Strategic Advisor|Tech Consultant|Technical Lead Consultant""".split("|")
REPORTING = {"Chief Executive Officer", "Chief Finance & Compliance Officer", "Chief Technology & Innovation Officer", "Head of Engineering", "Head of Operations", "Head of Product", "Head – Global Partnerships & Alliances", "Lead Back-End Engineer", "Manager Quality Assurance", "Principal Software Developer", "Senior Developer"}

# These identifiers are consumed by leave policy, balances, reports and the
# employee leave template.  Existing organisations may use their own non-empty
# codes, so seeding only fills a missing value and never replaces one.
STANDARD_LEAVE_TYPES = {
    "Annual Leave": ("ANNUAL", 22, "monthly"),
    "Sick Leave": ("SICK", 7, "annual"),
    "Maternity Leave": ("MATERNITY", 84, "event"),
    "Paternity Leave": ("PATERNITY", 3, "event"),
    "Leave Without Pay": ("LWP", 0, "none"),
    "Compassionate Leave": ("COMPASSIONATE", 0, "annual"),
    "Off in Lieu": ("OFF_IN_LIEU", 0, "annual"),
    "WFH": ("WFH", 0, "annual"),
}

STANDARD_REQUEST_TYPES = {
    "Change Attendance": "Request a reviewed correction to an official check-in or check-out record.",
}

def seed_reference_data(password):
    for name in DESIGNATIONS:
        item = Designation.query.filter_by(name=name).first() or Designation(name=name)
        item.is_reporting_officer_designation = name in REPORTING
        db.session.add(item)
    admin = User.query.filter_by(username="admin").first()
    if admin is None:
        admin = User(username="admin", must_change_password=True, is_administrator=True)
        admin.set_password(password)
        db.session.add(admin)
        db.session.flush()
    if admin.employee_profile is None:
        db.session.add(
            EmployeeProfile(
                user_id=admin.id,
                employee_code="PL-ADMIN-001",
                full_name="Pointlabs Administrator",
            )
        )
    for name, (code, days, accrual) in STANDARD_LEAVE_TYPES.items():
        item = LeaveType.query.filter_by(name=name).first() or LeaveType(name=name)
        if not (item.code or "").strip():
            item.code = code
        item.default_days, item.accrual_method = days, accrual
        item.requires_manager_approval = True
        db.session.add(item)
    for name, description in STANDARD_REQUEST_TYPES.items():
        if RequestType.query.filter_by(name=name).first() is None:
            db.session.add(RequestType(name=name, description=description))
    db.session.commit()
