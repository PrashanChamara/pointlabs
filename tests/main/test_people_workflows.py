from io import BytesIO

from app.extensions import db
from app.models.user import EmployeeProfile, User
from app.services.seed import seed_reference_data


def sign_in(client, user):
    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)
        session["_fresh"] = True


def test_dashboard_uses_time_aware_greeting(client, app):
    with app.app_context():
        seed_reference_data("admin123")
        admin = User.query.filter_by(username="admin").one()
        sign_in(client, admin)
    response = client.get("/")
    assert response.status_code == 200
    assert b"Good " in response.data
    assert b'class="mobile-nav"' not in response.data
    assert b'one-lockup' not in response.data
    assert b'mobile-wordmark' not in response.data
    assert b'data-menu-close' in response.data
    assert b'app-identity' in response.data
    assert response.data.count(b'brand-logo-frame') == 2


def test_dashboard_handles_leap_day_birthdays_in_non_leap_years(client, app):
    from datetime import date

    with app.app_context():
        seed_reference_data("admin123")
        admin = User.query.filter_by(username="admin").one()
        employee = User(username="leapday", must_change_password=False)
        employee.set_password("password")
        db.session.add(employee)
        db.session.flush()
        db.session.add(EmployeeProfile(user_id=employee.id, full_name="Leap Day", date_of_birth=date(2000, 2, 29)))
        db.session.commit()
        sign_in(client, admin)

    assert client.get("/").status_code == 200


def test_administrator_directory_renders_for_profiles_with_reporting_relations(client, app):
    with app.app_context():
        seed_reference_data("admin123")
        admin = User.query.filter_by(username="admin").one()
        sign_in(client, admin)
    response = client.get("/admin/employees")
    assert response.status_code == 200
    assert b"Employee list" in response.data


def test_employee_search_accepts_empty_and_partial_filters_without_a_server_error(client, app):
    with app.app_context():
        seed_reference_data("admin123")
        admin = User.query.filter_by(username="admin").one()
        employee = User(username="mira", email="mira@example.test", must_change_password=False)
        employee.set_password("password")
        db.session.add(employee)
        db.session.flush()
        db.session.add(EmployeeProfile(user_id=employee.id, full_name="Mira Patel", employee_code="PL-002"))
        db.session.commit()
        sign_in(client, admin)

    response = client.get("/admin/employees?q=Mira&designation_id=&department_id=")

    assert response.status_code == 200
    assert b"Mira Patel" in response.data
    assert b"No employees match" not in response.data


def test_administrator_can_upload_document_for_an_employee(client, app):
    with app.app_context():
        seed_reference_data("admin123")
        admin = User.query.filter_by(username="admin").one()
        employee = User(username="mira", email="mira@example.test", must_change_password=False)
        employee.set_password("password")
        db.session.add(employee)
        db.session.flush()
        db.session.add(EmployeeProfile(user_id=employee.id, full_name="Mira Patel", employee_code="PL-002"))
        db.session.commit()
        employee_id = employee.id
        sign_in(client, admin)
    response = client.post(
        "/documents",
        data={
            "employee_user_id": str(employee_id),
            "category": "Identity",
            "file": (BytesIO(b"%PDF-1.4 test"), "id.pdf"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 302
    with app.app_context():
        from app.models.hr import EmployeeDocument

        assert EmployeeDocument.query.one().user_id == employee_id


def test_message_is_stored_for_selected_recipient(client, app):
    with app.app_context():
        seed_reference_data("admin123")
        admin = User.query.filter_by(username="admin").one()
        employee = User(username="mira", must_change_password=False)
        employee.set_password("password")
        db.session.add(employee)
        db.session.flush()
        db.session.add(EmployeeProfile(user_id=employee.id, full_name="Mira Patel"))
        db.session.commit()
        employee_id = employee.id
        sign_in(client, admin)
    response = client.post("/messages", data={"recipient_id": employee_id, "body": "Welcome to Pointlabs One."})
    assert response.status_code == 302
    with app.app_context():
        from app.models.hr import DirectMessage

        message = DirectMessage.query.one()
        assert message.recipient_id == employee_id
        assert message.body == "Welcome to Pointlabs One."


def test_approved_leave_can_be_cancelled_without_double_deducting_balance(client, app):
    from datetime import date
    from app.models.hr import LeaveRequest, LeaveType

    with app.app_context():
        seed_reference_data("admin123")
        admin = User.query.filter_by(username="admin").one()
        admin.employee_profile.date_of_joining = date(2025, 1, 1)
        annual = LeaveType.query.filter_by(code="ANNUAL").one()
        request_item = LeaveRequest(
            user_id=admin.id,
            leave_type_id=annual.id,
            start_date=date(2026, 9, 8),
            end_date=date(2026, 9, 8),
            days=1,
            status="approved",
            balance_applied=True,
        )
        db.session.add(request_item)
        db.session.commit()
        request_id = request_item.id
        sign_in(client, admin)

    response = client.post(f"/leave/{request_id}/cancel")
    assert response.status_code == 302
    response = client.post(f"/leave/{request_id}/approve-cancellation")
    assert response.status_code == 302
    with app.app_context():
        item = db.session.get(LeaveRequest, request_id)
        assert item.status == "cancelled"
        assert item.balance_applied is False
