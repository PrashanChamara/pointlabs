"""Regression coverage for the simple reporting-officer approval model."""

from datetime import date

from flask import g, has_app_context
from app.extensions import db
from app.models.hr import LeaveRequest, LeaveType
from app.models.organization import Designation
from app.models.user import EmployeeProfile, User


def _user(username, designation, reporting_officer=None):
    user = User(username=username, must_change_password=False)
    user.set_password("test-password")
    db.session.add(user)
    db.session.flush()
    db.session.add(EmployeeProfile(
        user_id=user.id,
        full_name=username.replace("-", " ").title(),
        designation_id=designation.id,
        reporting_officer_id=reporting_officer.id if reporting_officer else None,
        date_of_joining=date(2025, 1, 1),
    ))
    db.session.flush()
    return user


def _sign_in(client, user):
    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)
        session["_fresh"] = True
    if has_app_context():
        g.pop("_login_user", None)


def test_designation_flags_drive_supervisor_and_admin_capabilities(app):
    with app.app_context():
        employee_title = Designation(name="Engineer")
        supervisor_title = Designation(
            name="Engineering Lead", is_reporting_officer_designation=True,
        )
        admin_title = Designation(name="Head of People", is_admin_designation=True)
        db.session.add_all((employee_title, supervisor_title, admin_title))
        db.session.flush()

        employee = _user("employee", employee_title)
        supervisor = _user("supervisor", supervisor_title)
        administrator = _user("administrator", admin_title)

        assert employee.has_hr_access is False
        assert supervisor.has_hr_access is True
        assert supervisor.can_manage_configuration is False
        assert supervisor.can_approve_requests is True
        assert administrator.has_hr_access is True
        assert administrator.can_manage_configuration is True


def test_reporting_officer_can_refer_leave_to_designation_and_next_holder_can_approve(app):
    from app.models.hr import DesignationApprovalAction, DesignationApprovalAssignment, DesignationApprovalCase
    from app.services.designation_approvals import act_on_approval_case, start_designation_approval

    with app.app_context():
        employee_title = Designation(name="Back-End Engineer")
        lead_title = Designation(name="Lead Back-End Engineer", is_reporting_officer_designation=True)
        head_title = Designation(name="Head of Operations", is_reporting_officer_designation=True)
        db.session.add_all((employee_title, lead_title, head_title))
        db.session.flush()
        lead = _user("lead", lead_title)
        requester = _user("requester", employee_title, lead)
        head = _user("head", head_title)
        leave_type = LeaveType(name="Annual Leave", code="DESIGNATION-ANNUAL", default_days=22)
        db.session.add(leave_type)
        db.session.flush()
        leave = LeaveRequest(
            user_id=requester.id, leave_type_id=leave_type.id,
            start_date=date(2026, 10, 1), end_date=date(2026, 10, 1), days=1,
        )
        db.session.add(leave)
        db.session.flush()

        case = start_designation_approval("leave", leave.id, requester)
        db.session.commit()
        assert case.current_designation_id == lead_title.id
        assert DesignationApprovalAssignment.query.filter_by(case_id=case.id, assignee_id=lead.id, status="pending").count() == 1

        act_on_approval_case(case, lead, "refer", "Please complete the final review.", head_title.id)
        db.session.commit()
        assert DesignationApprovalAssignment.query.filter_by(case_id=case.id, assignee_id=head.id, status="pending").count() == 1
        action = DesignationApprovalAction.query.filter_by(case_id=case.id, action="referred").one()
        assert action.comment == "Please complete the final review."

        result = act_on_approval_case(case, head, "approved", "Approved")
        db.session.commit()
        assert result == "approved"
        assert db.session.get(DesignationApprovalCase, case.id).status == "approved"


def test_approver_can_return_case_to_creator_or_previous_approver(app):
    from app.models.hr import DesignationApprovalAssignment
    from app.services.designation_approvals import act_on_approval_case, start_designation_approval

    with app.app_context():
        employee_title = Designation(name="Product Engineer")
        lead_title = Designation(name="Product Lead", is_reporting_officer_designation=True)
        head_title = Designation(name="Product Head", is_reporting_officer_designation=True)
        db.session.add_all((employee_title, lead_title, head_title))
        db.session.flush()
        lead = _user("product-lead", lead_title)
        requester = _user("product-requester", employee_title, lead)
        head = _user("product-head", head_title)

        case = start_designation_approval("other_request", 9001, requester)
        act_on_approval_case(case, lead, "refer", "Please review.", head_title.id)
        act_on_approval_case(case, head, "return_to_previous", "Please check the dates again.")
        db.session.commit()
        assert DesignationApprovalAssignment.query.filter_by(case_id=case.id, assignee_id=lead.id, status="pending").count() == 1

        act_on_approval_case(case, lead, "return_to_requester", "Add the handover plan.")
        db.session.commit()
        assert case.status == "more_information_required"
        assert case.awaiting_response_from_id == requester.id


def test_leave_submission_and_designation_referral_use_the_approval_inbox(client, app):
    from app.models.hr import DesignationApprovalCase

    with app.app_context():
        employee_title = Designation(name="Platform Engineer")
        lead_title = Designation(name="Platform Lead", is_reporting_officer_designation=True)
        head_title = Designation(name="Operations Head", is_reporting_officer_designation=True)
        db.session.add_all((employee_title, lead_title, head_title))
        db.session.flush()
        lead = _user("route-lead", lead_title)
        requester = _user("route-requester", employee_title, lead)
        head = _user("route-head", head_title)
        lwp = LeaveType(name="Leave Without Pay", code="LWP", default_days=0)
        db.session.add(lwp)
        db.session.commit()
        requester_id, lead_id, head_id, head_title_id, lwp_id = (
            requester.id, lead.id, head.id, head_title.id, lwp.id,
        )

    with app.app_context():
        requester = db.session.get(User, requester_id)
    _sign_in(client, requester)
    response = client.post("/leave", data={
        "leave_type": lwp_id,
        "start_date": "2026-10-05",
        "end_date": "2026-10-05",
        "reason": "Family appointment",
    })
    assert response.status_code == 302
    with app.app_context():
        case = DesignationApprovalCase.query.one()
        assert case.requester_id == requester.id
        case_id = case.id

    with app.app_context():
        lead = db.session.get(User, lead_id)
    _sign_in(client, lead)
    response = client.get("/approvals")
    assert response.status_code == 200
    assert b"Family appointment" in response.data
    response = client.post(f"/approvals/designation/{case_id}/refer", data={
        "designation_id": head_title_id,
        "comment": "Please make the final decision.",
    })
    assert response.status_code == 302

    with app.app_context():
        head = db.session.get(User, head_id)
    _sign_in(client, head)
    response = client.get("/approvals")
    assert response.status_code == 200
    assert b"Please make the final decision" not in response.data
    assert b"Leave Without Pay" in response.data
    response = client.post(
        f"/approvals/designation/{case_id}/approved",
        data={"comment": "Approved after operations review."},
    )
    assert response.status_code == 302
    with app.app_context():
        leave = LeaveRequest.query.one()
        assert leave.status == "approved"
        assert leave.approver_id == head_id
