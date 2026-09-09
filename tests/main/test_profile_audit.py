from flask import g, has_app_context

from app.extensions import db
from app.models.hr import AuditEvent
from app.models.user import EmployeeProfile, User


def test_self_service_profile_update_records_non_sensitive_audit_summary(client, app):
    with app.app_context():
        user = User(username="profile-audit-user", email="old@example.test", must_change_password=False)
        user.set_password("password")
        db.session.add(user); db.session.flush()
        db.session.add(EmployeeProfile(user_id=user.id, full_name="Profile Audit User")); db.session.commit()
        with client.session_transaction() as session:
            session["_user_id"] = str(user.id); session["_fresh"] = True
        if has_app_context():
            g.pop("_login_user", None)
    response = client.post("/profile", data={"preferred_name": "Audit", "phone": "123", "personal_email": "private@example.test", "address": "New address", "email": "new@example.test"})
    assert response.status_code == 302
    with app.app_context():
        event = AuditEvent.query.filter_by(action="self_service_updated").one()
        assert "personal email" in event.summary and "private@example.test" not in event.summary
