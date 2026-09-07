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


def test_administrator_directory_renders_for_profiles_with_reporting_relations(client, app):
    with app.app_context():
        seed_reference_data("admin123")
        admin = User.query.filter_by(username="admin").one()
        sign_in(client, admin)
    response = client.get("/admin/employees")
    assert response.status_code == 200
    assert b"Employee list" in response.data


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
