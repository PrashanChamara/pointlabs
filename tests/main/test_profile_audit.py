from io import BytesIO

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


def test_employee_can_upload_a_validated_profile_photo(client, app):
    with app.app_context():
        user = User(username="photo-user", email="photo@example.test", must_change_password=False)
        user.set_password("password")
        db.session.add(user); db.session.flush()
        db.session.add(EmployeeProfile(user_id=user.id, full_name="Photo User")); db.session.commit()
        with client.session_transaction() as session:
            session["_user_id"] = str(user.id); session["_fresh"] = True
        if has_app_context():
            g.pop("_login_user", None)

    response = client.post(
        "/profile",
        data={"action": "photo", "photo": (BytesIO(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\xd7c\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb1\x00\x00\x00\x00IEND\xaeB`\x82"
        ), "portrait.png")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 302
    with app.app_context():
        profile = User.query.filter_by(username="photo-user").one().employee_profile
        assert profile.profile_photo_stored_path.endswith(".webp")
    response = client.get("/profile")
    assert response.status_code == 200
    assert b"Change photo" in response.data


def test_employee_profile_change_notifies_administrators(client, app):
    from app.models.hr import Notification
    from app.services.seed import seed_reference_data

    with app.app_context():
        seed_reference_data("admin123")
        employee = User(username="profile-change", email="before@example.test", must_change_password=False)
        employee.set_password("password")
        db.session.add(employee); db.session.flush()
        db.session.add(EmployeeProfile(user_id=employee.id, full_name="Profile Change")); db.session.commit()
        with client.session_transaction() as session:
            session["_user_id"] = str(employee.id); session["_fresh"] = True
        if has_app_context():
            g.pop("_login_user", None)

    response = client.post("/profile", data={
        "preferred_name": "Changed", "phone": "123", "personal_email": "personal@example.test",
        "address": "Updated address", "email": "after@example.test",
    })

    assert response.status_code == 302
    with app.app_context():
        admin = User.query.filter_by(username="admin").one()
        notification = Notification.query.filter_by(user_id=admin.id).one()
        assert "Profile Change updated their profile" in notification.message


def test_profile_photo_rejects_non_image_uploads(client, app):
    with app.app_context():
        user = User(username="unsafe-photo", email="unsafe@example.test", must_change_password=False)
        user.set_password("password")
        db.session.add(user); db.session.flush()
        db.session.add(EmployeeProfile(user_id=user.id, full_name="Unsafe Photo")); db.session.commit()
        with client.session_transaction() as session:
            session["_user_id"] = str(user.id); session["_fresh"] = True
        if has_app_context():
            g.pop("_login_user", None)

    response = client.post(
        "/profile",
        data={"action": "photo", "photo": (BytesIO(b"#!/bin/sh\necho unsafe"), "portrait.sh")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 302
    with app.app_context():
        assert User.query.filter_by(username="unsafe-photo").one().employee_profile.profile_photo_stored_path is None
