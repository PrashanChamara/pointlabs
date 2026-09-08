"""Tests for the visible HR operations workflows, not only their data models."""

from datetime import date

from flask import g, has_app_context

from app.extensions import db
from app.models.hr import LeaveBalanceAdjustment, LeaveRequest, LeaveType, OtherRequest, PublicHoliday
from app.models.organization import Entity, Location
from app.models.user import EmployeeProfile, User
from app.services.hr import leave_days_for_profile
from app.services.seed import seed_reference_data


def sign_in(client, user):
    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)
        session["_fresh"] = True
    if has_app_context():
        g.pop("_login_user", None)


def make_employee(app, username, *, manager_id=None):
    with app.app_context():
        user = User(username=username, email=f"{username}@example.test", must_change_password=False)
        user.set_password("password")
        db.session.add(user)
        db.session.flush()
        db.session.add(EmployeeProfile(
            user_id=user.id, full_name=username.title(), employee_code=f"EMP-{user.id:03d}",
            date_of_joining=date(2025, 1, 1), reporting_officer_id=manager_id,
        ))
        db.session.commit()
        return user.id


def test_hr_can_adjust_leave_balances_with_an_audit_record(client, app):
    with app.app_context():
        seed_reference_data("admin123")
        admin = User.query.filter_by(username="admin").one()
        annual = LeaveType.query.filter_by(code="ANNUAL").one()
        sign_in(client, admin)
    employee_id = make_employee(app, "balanceowner")

    response = client.post("/admin/leave-balances", data={
        "user_id": employee_id, "leave_type_id": annual.id, "calendar_year": "2026",
        "days": "2.5", "reason": "Opening balance confirmed by HR",
    })
    assert response.status_code == 302
    with app.app_context():
        adjustment = LeaveBalanceAdjustment.query.one()
        assert adjustment.days == 2.5
        assert adjustment.reason == "Opening balance confirmed by HR"
        assert adjustment.changed_by_id == admin.id
    assert client.get(f"/admin/leave-balances?year=2026&user_id={employee_id}").status_code == 200


def test_employee_can_edit_own_pending_leave_but_not_another_employee_leave(client, app):
    with app.app_context():
        seed_reference_data("admin123")
        annual = LeaveType.query.filter_by(code="ANNUAL").one()
    owner_id = make_employee(app, "leaveeditor")
    other_id = make_employee(app, "leaveother")
    with app.app_context():
        request_item = LeaveRequest(
            user_id=owner_id, leave_type_id=annual.id, start_date=date(2026, 9, 14),
            end_date=date(2026, 9, 14), days=1, status="submitted",
        )
        db.session.add(request_item)
        db.session.commit()
        request_id = request_item.id
        owner, other = db.session.get(User, owner_id), db.session.get(User, other_id)

    sign_in(client, owner)
    assert client.post(f"/leave/{request_id}/edit", data={
        "leave_type": annual.id, "start_date": "2026-09-15", "end_date": "2026-09-16", "reason": "Updated handover",
    }).status_code == 302
    with app.app_context():
        item = db.session.get(LeaveRequest, request_id)
        assert item.start_date == date(2026, 9, 15)
        assert item.days == 2
        assert item.reason == "Updated handover"
    sign_in(client, other)
    assert client.post(f"/leave/{request_id}/edit", data={
        "leave_type": annual.id, "start_date": "2026-09-17", "end_date": "2026-09-17",
    }).status_code == 403


def test_employee_can_edit_own_hr_request_and_hr_sees_it_in_approvals(client, app):
    with app.app_context():
        seed_reference_data("admin123")
        admin = User.query.filter_by(username="admin").one()
        sign_in(client, admin)
    employee_id = make_employee(app, "requesteditor")
    with app.app_context():
        employee = db.session.get(User, employee_id)
    sign_in(client, employee)
    response = client.post("/requests", data={"category": "Salary Certificate", "subject": "Bank", "details": "Initial details"})
    assert response.status_code == 302
    with app.app_context():
        item = OtherRequest.query.one()
        request_id = item.id
    assert client.post(f"/requests/{request_id}", data={
        "action": "edit", "subject": "Updated bank certificate", "details": "Updated details",
    }).status_code == 302
    with app.app_context():
        item = db.session.get(OtherRequest, request_id)
        assert item.subject == "Updated bank certificate"
        assert item.details == "Updated details"
        admin = User.query.filter_by(username="admin").one()
    sign_in(client, admin)
    response = client.get("/approvals")
    assert response.status_code == 200
    assert b"Updated bank certificate" in response.data


def test_reporting_manager_can_use_the_approval_inbox_for_direct_report_leave(client, app):
    with app.app_context():
        seed_reference_data("admin123")
    manager_id = make_employee(app, "manager")
    employee_id = make_employee(app, "directreport", manager_id=manager_id)
    with app.app_context():
        annual = LeaveType.query.filter_by(code="ANNUAL").one()
        item = LeaveRequest(user_id=employee_id, leave_type_id=annual.id, start_date=date(2026, 9, 21), end_date=date(2026, 9, 21), days=1, status="submitted")
        db.session.add(item)
        db.session.commit()
        manager = db.session.get(User, manager_id)
        request_id = item.id
    sign_in(client, manager)
    response = client.get("/approvals")
    assert response.status_code == 200
    assert b"Directreport" in response.data
    assert client.post(f"/leave/{request_id}/approve", data={"comment": "Approved"}).status_code == 302
    with app.app_context():
        assert db.session.get(LeaveRequest, request_id).status == "approved"


def test_entity_and_location_holidays_apply_only_to_matching_employee(client, app):
    with app.app_context():
        entity = Entity(name="Pointlabs UAE", country_code="AE")
        db.session.add(entity)
        db.session.flush()
        dubai = Location(name="Dubai", country_code="AE", entity_id=entity.id)
        colombo = Location(name="Colombo", country_code="LK")
        db.session.add_all((dubai, colombo))
        db.session.flush()
        db.session.add(PublicHoliday(name="UAE National Day", holiday_date=date(2026, 12, 2), entity_id=entity.id, location_id=dubai.id))
        db.session.commit()
        dubai_user = User(username="dubaiuser", must_change_password=False)
        colombo_user = User(username="colombouser", must_change_password=False)
        dubai_user.set_password("password"); colombo_user.set_password("password")
        db.session.add_all((dubai_user, colombo_user)); db.session.flush()
        dubai_profile = EmployeeProfile(user_id=dubai_user.id, full_name="Dubai User", entity_id=entity.id, location_id=dubai.id)
        colombo_profile = EmployeeProfile(user_id=colombo_user.id, full_name="Colombo User", location_id=colombo.id)
        db.session.add_all((dubai_profile, colombo_profile)); db.session.commit()
        assert leave_days_for_profile(dubai_profile, date(2026, 12, 2), date(2026, 12, 2)) == 0
        assert leave_days_for_profile(colombo_profile, date(2026, 12, 2), date(2026, 12, 2)) == 1


def test_operational_admin_pages_render_with_the_new_workflows(client, app):
    with app.app_context():
        seed_reference_data("admin123")
        admin = User.query.filter_by(username="admin").one()
        sign_in(client, admin)
    for path, expected in (
        ("/admin", b"Leave balances"),
        ("/admin/employees/new", b"Job title & approvals"),
        ("/admin/public-holidays", b"Holiday calendar"),
        ("/admin/payroll", b"Payroll & compensation"),
    ):
        response = client.get(path)
        assert response.status_code == 200
        assert expected in response.data
