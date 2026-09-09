from datetime import date

from flask import g, has_app_context

from app.extensions import db
from app.models.hr import ApprovalDecision, ApprovalWorkflow, ApprovalWorkflowStep, LeaveRequest, LeaveType
from app.models.organization import Designation
from app.models.user import EmployeeProfile, User
from app.services.workflows import decide, resubmit_after_more_information, start_workflow
from app.services.seed import seed_reference_data


def _user(name, designation=None):
    user = User(username=name, must_change_password=False)
    user.set_password("test-password")
    db.session.add(user); db.session.flush()
    db.session.add(EmployeeProfile(user_id=user.id, full_name=name.title(), designation_id=designation.id if designation else None, date_of_joining=date(2025, 1, 1)))
    db.session.flush()
    return user


def test_designation_workflow_runs_stages_in_order_and_preserves_decisions(app):
    with app.app_context():
        requester_designation = Designation(name="Engineer")
        manager_designation = Designation(name="Manager")
        director_designation = Designation(name="Director")
        db.session.add_all((requester_designation, manager_designation, director_designation)); db.session.flush()
        requester = _user("workflow-requester", requester_designation)
        manager = _user("workflow-manager", manager_designation)
        director = _user("workflow-director", director_designation)
        leave_type = LeaveType(name="Annual", code="WF-ANNUAL", default_days=22)
        db.session.add(leave_type); db.session.flush()
        leave = LeaveRequest(user_id=requester.id, leave_type_id=leave_type.id, start_date=date(2026, 10, 1), end_date=date(2026, 10, 1), days=1)
        workflow = ApprovalWorkflow(name="Sequential leave", applies_to="leave", is_active=True)
        db.session.add_all((leave, workflow)); db.session.flush()
        first = ApprovalWorkflowStep(workflow_id=workflow.id, step_order=1, approver_kind="designation", designation_id=manager_designation.id)
        second = ApprovalWorkflowStep(workflow_id=workflow.id, step_order=2, approver_kind="designation", designation_id=director_designation.id)
        db.session.add_all((first, second)); db.session.commit()
        instance = start_workflow(workflow, "leave", leave.id, requester)
        db.session.commit()
        initial = ApprovalDecision.query.one()
        assert initial.approver_id == manager.id
        _, terminal = decide(initial, manager, "approved", "Looks good")
        db.session.commit()
        assert terminal is None
        next_decision = ApprovalDecision.query.filter_by(status="pending").one()
        assert next_decision.approver_id == director.id
        instance, terminal = decide(next_decision, director, "approved", "Final approval")
        db.session.commit()
        assert terminal == "approved"
        assert instance.status == "approved"
        assert ApprovalDecision.query.filter_by(status="approved").count() == 2


def test_hr_can_open_workflow_studio(client, app):
    with app.app_context():
        seed_reference_data("admin123")
        admin = User.query.filter_by(username="admin").one()
    with client.session_transaction() as session:
        session["_user_id"] = str(admin.id)
        session["_fresh"] = True
    if has_app_context():
        g.pop("_login_user", None)
    response = client.get("/admin/workflows")
    assert response.status_code == 200
    assert b"Approval workflows" in response.data


def test_admin_can_archive_an_access_role_without_deleting_it(client, app):
    from app.models.organization import AccessRole
    with app.app_context():
        seed_reference_data("admin123")
        admin = User.query.filter_by(username="admin").one()
        role = AccessRole(name="Temporary reviewer")
        db.session.add(role); db.session.commit()
        role_id = role.id
        with client.session_transaction() as session:
            session["_user_id"] = str(admin.id); session["_fresh"] = True
    response = client.post(f"/admin/access-roles/{role_id}/toggle")
    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(AccessRole, role_id).is_active is False


def test_more_information_can_be_resubmitted_without_duplicate_route(app):
    with app.app_context():
        designation = Designation(name="Workflow HR")
        db.session.add(designation); db.session.flush()
        requester, approver = _user("clarify-requester"), _user("clarify-approver", designation)
        flow = ApprovalWorkflow(name="Clarification route", applies_to="other_request", is_active=True)
        db.session.add(flow); db.session.flush()
        db.session.add(ApprovalWorkflowStep(workflow_id=flow.id, step_order=1, approver_kind="designation", designation_id=designation.id)); db.session.commit()
        instance = start_workflow(flow, "other_request", 1001, requester); db.session.commit()
        decision = ApprovalDecision.query.one()
        decide(decision, approver, "more_information_required", "Please add dates")
        db.session.commit()
        assert instance.status == "more_information_required"
        assert resubmit_after_more_information(instance) is True
        db.session.commit()
        assert instance.status == "pending"
        assert ApprovalDecision.query.one().status == "pending"


def test_access_role_can_be_selected_as_an_approval_source(app):
    from app.models.organization import AccessRole
    with app.app_context():
        role = AccessRole(name="People approver", grants_hr_access=True)
        db.session.add(role); db.session.flush()
        requester, approver = _user("role-requester"), _user("role-approver")
        approver.access_role_id = role.id
        flow = ApprovalWorkflow(name="Role-based route", applies_to="leave")
        db.session.add(flow); db.session.flush()
        db.session.add(ApprovalWorkflowStep(workflow_id=flow.id, step_order=1, approver_kind="access_role", access_role_id=role.id)); db.session.commit()
        instance = start_workflow(flow, "leave", 2001, requester); db.session.commit()
        assert ApprovalDecision.query.filter_by(approval_instance_id=instance.id).one().approver_id == approver.id
