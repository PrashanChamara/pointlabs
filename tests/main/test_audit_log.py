from flask import g, has_app_context

from app.extensions import db
from app.models.hr import AuditEvent
from app.models.user import User
from app.services.seed import seed_reference_data


def _sign_in(client, user):
    with client.session_transaction() as session:
        session["_user_id"] = str(user.id); session["_fresh"] = True
    if has_app_context():
        g.pop("_login_user", None)


def test_audit_history_is_visible_to_admin(client, app):
    with app.app_context():
        seed_reference_data("admin123")
        admin = User.query.filter_by(username="admin").one()
        db.session.add(AuditEvent(actor_id=admin.id, entity_type="employee", entity_id=1, action="created", summary="Employee record created."))
        db.session.commit()
        _sign_in(client, admin)
    response = client.get("/admin/audit")
    assert response.status_code == 200 and b"Employee record created" in response.data


def test_audit_history_is_hidden_from_employee(client, app):
    with app.app_context():
        employee = User(username="audit-employee", must_change_password=False); employee.set_password("password")
        db.session.add(employee); db.session.commit()
        _sign_in(client, employee)
    assert client.get("/admin/audit").status_code == 403
