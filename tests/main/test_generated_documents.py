"""End-to-end coverage for private Pointlabs payroll and leave PDFs."""

from datetime import date
from pathlib import Path

from flask import g, has_app_context
from app.extensions import db
from app.models.hr import LeaveRequest, LeaveType, Payslip
from app.models.organization import Location
from app.models.user import EmployeeProfile, User
from app.services.email import send_leave_confirmation_email, send_payslip_email
from app.services.seed import seed_reference_data


def sign_in(client, user):
    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)
        session["_fresh"] = True
    # The shared app fixture intentionally holds an app context for each test.
    # Flask-Login caches the current user in ``g``; clear that cache when a test
    # deliberately switches actors so authorization is actually exercised.
    if has_app_context():
        g.pop("_login_user", None)


def make_employee(app, username, code, *, country="LK"):
    with app.app_context():
        user = User(username=username, email=f"{username}@example.test", must_change_password=False)
        user.set_password("password")
        db.session.add(user)
        db.session.flush()
        location = None
        if country == "AE":
            location = Location(name="Dubai", country_code="AE")
            db.session.add(location)
            db.session.flush()
        db.session.add(EmployeeProfile(
            user_id=user.id, full_name=f"{username.title()} Long Employee Name", employee_code=code,
            date_of_joining=date(2024, 1, 15), location_id=location.id if location else None,
        ))
        db.session.commit()
        return user.id


def add_compensation(client, employee_id, currency):
    return client.post(f"/admin/payroll/compensation/{employee_id}", data={
        "effective_date": "2026-07-01", "currency": currency, "basic_salary": "100000",
        "allowances": "10000", "other_earnings": "5000", "wht": "1000", "epf": "8000",
        "etf": "0", "paye": "2000", "other_deductions": "500",
    })


def generate_payslip(client, employee_id):
    return client.post(f"/admin/payroll/generate/{employee_id}", data={"year": "2026", "month": "7"})


def test_lk_and_uae_payslips_generate_private_nonempty_pdfs(client, app):
    with app.app_context():
        seed_reference_data("admin123")
        admin = User.query.filter_by(username="admin").one()
        sign_in(client, admin)
    lk_employee_id = make_employee(app, "lanka", "EMP001")
    ae_employee_id = make_employee(app, "dubai", "EMP002", country="AE")

    assert add_compensation(client, lk_employee_id, "LKR").status_code == 302
    assert generate_payslip(client, lk_employee_id).status_code == 302
    assert add_compensation(client, ae_employee_id, "AED").status_code == 302
    assert generate_payslip(client, ae_employee_id).status_code == 302

    with app.app_context():
        slips = Payslip.query.order_by(Payslip.user_id).all()
        assert len(slips) == 2
        assert [slip.template_country for slip in slips] == ["LK", "AE"]
        for slip in slips:
            path = Path(app.instance_path) / "generated" / "payslips" / slip.pdf_stored_path
            assert path.is_file() and path.stat().st_size > 1_000
            assert path.read_bytes().startswith(b"%PDF-")
            assert b"PAYSLIP" in path.read_bytes()
            assert slip.pdf_filename.startswith("Pointlabs_Payslip_2026-07_")
        assert b"Lanka Long Employee Name" in (Path(app.instance_path) / "generated" / "payslips" / slips[0].pdf_stored_path).read_bytes()


def test_payslip_download_is_limited_to_owner_or_hr(client, app):
    with app.app_context():
        seed_reference_data("admin123")
        admin = User.query.filter_by(username="admin").one()
        sign_in(client, admin)
    owner_id = make_employee(app, "owner", "EMP003")
    other_id = make_employee(app, "other", "EMP004")
    add_compensation(client, owner_id, "LKR")
    generate_payslip(client, owner_id)
    with app.app_context():
        payslip_id = Payslip.query.one().id
        owner = db.session.get(User, owner_id)
        other = db.session.get(User, other_id)
        admin = User.query.filter_by(username="admin").one()

    owner_client, other_client, hr_client = app.test_client(), app.test_client(), app.test_client()
    sign_in(owner_client, owner)
    assert owner_client.get(f"/payslips/{payslip_id}/download").status_code == 200
    sign_in(other_client, other)
    assert other_client.get(f"/payslips/{payslip_id}/download").status_code == 403
    sign_in(hr_client, admin)
    assert hr_client.get(f"/payslips/{payslip_id}/download").status_code == 200


def test_payslip_pdf_failure_is_recorded_without_claiming_delivery(client, app, monkeypatch):
    with app.app_context():
        seed_reference_data("admin123")
        admin = User.query.filter_by(username="admin").one()
        sign_in(client, admin)
    employee_id = make_employee(app, "brokenpdf", "EMP005")
    add_compensation(client, employee_id, "LKR")
    monkeypatch.setattr("app.main.routes.generate_payslip_pdf", lambda _: (_ for _ in ()).throw(RuntimeError("renderer unavailable")))
    assert generate_payslip(client, employee_id).status_code == 302
    with app.app_context():
        payslip = Payslip.query.one()
        assert payslip.status == "generation_failed"
        assert payslip.pdf_stored_path is None
        assert payslip.emailed_at is None
        assert payslip.pdf_generation_error


def test_approved_leave_generates_preserves_and_protects_confirmation_pdf(client, app):
    with app.app_context():
        seed_reference_data("admin123")
        admin = User.query.filter_by(username="admin").one()
        annual = LeaveType.query.filter_by(code="ANNUAL").one()
        owner_id = make_employee(app, "leaveowner", "EMP006")
        other_id = make_employee(app, "leaveother", "EMP007")
        request_item = LeaveRequest(
            user_id=owner_id, leave_type_id=annual.id, start_date=date(2026, 7, 6),
            end_date=date(2026, 7, 7), days=2, status="submitted",
        )
        db.session.add(request_item)
        db.session.commit()
        request_id = request_item.id
        assert request_item.confirmation_stored_path is None
        sign_in(client, admin)

    assert client.post(f"/leave/{request_id}/approve", data={"comment": "Approved."}).status_code == 302
    with app.app_context():
        request_item = db.session.get(LeaveRequest, request_id)
        owner = db.session.get(User, owner_id)
        other = db.session.get(User, other_id)
        admin = User.query.filter_by(username="admin").one()
        assert request_item.status == "approved"
        assert request_item.confirmation_reference.startswith("PL-LEAVE-")
        assert request_item.confirmation_reference != f"PL-LEAVE-2026-{request_id:06d}"
        path = Path(app.instance_path) / "generated" / "leave-confirmations" / request_item.confirmation_stored_path
        assert path.is_file() and path.read_bytes().startswith(b"%PDF-")
        assert b"LEAVE CONFIRMATION" in path.read_bytes()
        original_path = request_item.confirmation_stored_path

    owner_client, other_client, hr_client = app.test_client(), app.test_client(), app.test_client()
    sign_in(owner_client, owner)
    assert owner_client.get(f"/leave/{request_id}/confirmation.pdf").status_code == 200
    sign_in(other_client, other)
    assert other_client.get(f"/leave/{request_id}/confirmation.pdf").status_code == 403
    sign_in(hr_client, admin)
    assert hr_client.get(f"/leave/{request_id}/confirmation.pdf").status_code == 200
    sign_in(owner_client, owner)
    assert owner_client.post(f"/leave/{request_id}/cancel").status_code == 302
    sign_in(hr_client, admin)
    assert hr_client.post(f"/leave/{request_id}/approve-cancellation").status_code == 302
    with app.app_context():
        request_item = db.session.get(LeaveRequest, request_id)
        assert request_item.status == "cancelled"
        assert request_item.confirmation_stored_path == original_path
        assert (Path(app.instance_path) / "generated" / "leave-confirmations" / original_path).is_file()


def test_branded_email_helpers_attach_the_private_pdf(app, monkeypatch, tmp_path):
    document = tmp_path / "document.pdf"
    document.write_bytes(b"%PDF-1.4 sample")
    sent = []

    class FakeSMTP:
        def __init__(self, *_):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def starttls(self):
            return None

        def login(self, *_):
            return None

        def send_message(self, message):
            sent.append(message)

    with app.app_context():
        app.config.update(SMTP_HOST="smtp.example.test", SMTP_FROM="hr@example.test")
        monkeypatch.setattr("app.services.email.smtplib.SMTP", FakeSMTP)
        assert send_payslip_email("employee@example.test", "Mira Patel", "July 2026", document, "payslip.pdf")
        assert send_leave_confirmation_email("employee@example.test", "Mira Patel", "Annual Leave", "06–07 July 2026", document, "leave.pdf")

    assert len(sent) == 2
    for message in sent:
        attachments = list(message.iter_attachments())
        assert len(attachments) == 1
        assert attachments[0].get_content_type() == "application/pdf"
        assert attachments[0].get_payload(decode=True).startswith(b"%PDF-")
