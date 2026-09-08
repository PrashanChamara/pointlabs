from app.extensions import db
from app.models.organization import Designation
from app.models.user import EmployeeProfile, User
from app.models.hr import LeaveType

DESIGNATIONS = """Chief Business Officer|Chief Executive Officer|Chief Finance & Compliance Officer|Chief Technology & Innovation Officer|Consultant - Partnership|Consultant UI UX Designer|Consultant – IT Program Manager|Country Head South Asia|Finance Manager|Frontend Developer|Gen AI Engineer|Head of Engineering|Head of Operations|Head of Product|Head – Global Partnerships & Alliances|Intern Product Management|Lead Back-End Engineer|Manager Quality Assurance|Manager, Partnerships & Operations|Marketing Support|Merchant Partnership Manager|Principal Engineering Consultant|Principal Quality Assurance Consultant|Principal Software Developer|Product Designer|Quality Assurance Consultant|Senior Developer|Snr Partnership Manager|Solution Architect|Sr Front-End Developer|Strategic Advisor|Tech Consultant|Technical Lead Consultant""".split("|")
REPORTING = {"Chief Executive Officer", "Chief Finance & Compliance Officer", "Chief Technology & Innovation Officer", "Head of Engineering", "Head of Operations", "Head of Product", "Head – Global Partnerships & Alliances", "Lead Back-End Engineer", "Manager Quality Assurance", "Principal Software Developer", "Senior Developer"}

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
    leave_types = {
        "Annual Leave": ("ANNUAL", 22, "monthly"),
        "Sick Leave": ("SICK", 7, "annual"),
        "Maternity Leave": ("MATERNITY", 84, "event"),
        "Paternity Leave": ("PATERNITY", 3, "event"),
        "Leave Without Pay": ("LWP", 0, "none"),
        "Compassionate Leave": ("COMPASSIONATE", 0, "annual"),
        "Off in Lieu": ("OFF_IN_LIEU", 0, "annual"),
        "WFH": ("WFH", 0, "annual"),
    }
    for name, (code, days, accrual) in leave_types.items():
        item = LeaveType.query.filter_by(name=name).first() or LeaveType(name=name)
        item.code, item.default_days, item.accrual_method = code, days, accrual
        item.requires_manager_approval = True
        db.session.add(item)
    db.session.commit()
