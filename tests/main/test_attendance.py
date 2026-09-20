from datetime import date, datetime

from flask import g, has_app_context

from app.extensions import db
from app.models.hr import AttendanceChangeRequest, AttendanceRecord, Notification, OtherRequest, RequestType
from app.models.user import EmployeeProfile, User
from app.services.seed import seed_reference_data


def _sign_in(client, user):
    with client.session_transaction() as session:
        session["_user_id"] = str(user.id); session["_fresh"] = True
    if has_app_context():
        g.pop("_login_user", None)
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


def test_attendance_correction_is_an_hr_request_and_only_approval_updates_the_record(client, app):
    admin_client = app.test_client()
    with app.app_context():
        seed_reference_data("admin123")
        admin = User.query.filter_by(username="admin").one()
        user = User(username="attendance-correction-user", email="correction@example.test", must_change_password=False)
        user.set_password("password")
        db.session.add(user)
        db.session.flush()
        db.session.add(EmployeeProfile(user_id=user.id, full_name="Attendance Correction User"))
        db.session.commit()
        user_id, admin_id = user.id, admin.id
        request_type_id = RequestType.query.filter_by(name="Change Attendance").one().id
        _sign_in(client, user)

    response = client.post("/requests", data={
        "request_type_id": request_type_id,
        "attendance_date": "2026-09-20",
        "requested_check_in_time": "09:00",
        "requested_check_out_time": "17:30",
        "details": "My access card was unavailable when I arrived.",
    })
    assert response.status_code == 302
    with app.app_context():
        change = AttendanceChangeRequest.query.one()
        assert change.status == "submitted"
        assert change.request.status == "submitted"
        assert AttendanceRecord.query.count() == 0
        assert Notification.query.filter_by(user_id=admin_id).count() == 1
        change_id = change.id
        admin = db.session.get(User, admin_id)
        assert admin.has_hr_access

    assert admin_client.post("/auth/login", data={"username": "admin", "password": "admin123"}).status_code == 302
    assert admin_client.get("/admin/attendance.csv").status_code == 200
    response = admin_client.post(f"/approvals/attendance-change/{change_id}", data={"action": "approved", "comment": "Approved after access-log review."})
    assert response.status_code == 302
    repeat_response = admin_client.post(f"/approvals/attendance-change/{change_id}", data={"action": "approved"})
    assert repeat_response.status_code == 302
    assert f"/requests/".encode() in repeat_response.headers["Location"].encode()
    with app.app_context():
        change = db.session.get(AttendanceChangeRequest, change_id)
        record = AttendanceRecord.query.one()
        request_item = OtherRequest.query.one()
        assert change.status == "approved"
        assert change.reviewer_id == admin_id
        assert request_item.status == "approved"
        assert record.user_id == user_id
        assert record.checked_in_at.strftime("%H:%M") == "09:00"
        assert record.checked_out_at.strftime("%H:%M") == "17:30"
        assert Notification.query.filter_by(user_id=user_id).count() == 1


def test_reports_surface_selected_period_attendance_and_csv_export(client, app):
    with app.app_context():
        seed_reference_data("admin123")
        admin = User.query.filter_by(username="admin").one()
        user = User(username="attendance-report-user", must_change_password=False)
        user.set_password("password")
        db.session.add(user)
        db.session.flush()
        db.session.add(EmployeeProfile(user_id=user.id, full_name="Attendance Report User"))
        db.session.add(AttendanceRecord(
            user_id=user.id,
            work_date=date(2026, 9, 20),
            checked_in_at=datetime(2026, 9, 20, 9, 0),
            checked_out_at=datetime(2026, 9, 20, 17, 30),
        ))
        db.session.commit()
        _sign_in(client, admin)

    response = client.get("/reports?from_date=2026-09-01&to_date=2026-09-30")
    assert response.status_code == 200
    assert b"ATTENDANCE REPORT" in response.data
    assert b"Attendance Report User" in response.data
    assert b"Attendance CSV" in response.data
    export = client.get("/admin/attendance.csv?from_date=2026-09-01&to_date=2026-09-30")
    assert export.status_code == 200
    assert b"Attendance Report User" in export.data


def test_attendance_page_has_only_system_capture_actions(client, app):
    with app.app_context():
        user = User(username="attendance-page-user", must_change_password=False)
        user.set_password("password")
        db.session.add(user)
        db.session.flush()
        db.session.add(EmployeeProfile(user_id=user.id, full_name="Attendance Page User"))
        db.session.commit()
        _sign_in(client, user)

    response = client.get("/attendance")
    assert response.status_code == 200
    assert b"Check in now" in response.data
    assert b'name="attendance_date"' not in response.data
    assert b'name="requested_check_in_time"' not in response.data
