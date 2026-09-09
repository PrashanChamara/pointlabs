from flask import g, has_app_context

from app.extensions import db
from app.models.hr import AttendanceRecord
from app.models.user import EmployeeProfile, User
from app.services.seed import seed_reference_data


def _sign_in(client, user):
    with client.session_transaction() as session:
        session["_user_id"] = str(user.id); session["_fresh"] = True
    if has_app_context():
        g.pop("_login_user", None)


def test_employee_can_check_in_and_out_once_per_day(client, app):
    with app.app_context():
        user = User(username="attendance-user", must_change_password=False); user.set_password("password")
        db.session.add(user); db.session.flush(); db.session.add(EmployeeProfile(user_id=user.id, full_name="Attendance User")); db.session.commit()
        _sign_in(client, user)
    assert client.post("/attendance", data={"action": "check-in", "note": "Remote"}).status_code == 302
    assert client.post("/attendance", data={"action": "check-in"}).status_code == 302
    assert client.post("/attendance", data={"action": "check-out", "note": "Handover done"}).status_code == 302
    with app.app_context():
        record = AttendanceRecord.query.one()
        assert record.checked_out_at is not None and record.check_in_note == "Remote"


def test_attendance_export_rejects_non_hr_employee(client, app):
    with app.app_context():
        seed_reference_data("admin123")
        user = User(username="attendance-export-user", must_change_password=False); user.set_password("password")
        db.session.add(user); db.session.flush(); user_id = user.id
        db.session.add(EmployeeProfile(user_id=user_id, full_name="Export User")); db.session.commit()
    with app.app_context():
        _sign_in(client, db.session.get(User, user_id))
    assert client.get("/admin/attendance.csv").status_code == 403
