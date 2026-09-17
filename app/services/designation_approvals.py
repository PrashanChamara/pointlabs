"""Designation and reporting-officer based approval routing."""

from datetime import datetime

from app.extensions import db
from app.models.hr import (
    DesignationApprovalAction,
    DesignationApprovalAssignment,
    DesignationApprovalCase,
)
from app.models.organization import Designation
from app.models.user import EmployeeProfile, User


def _designation_for(user):
    profile = user.employee_profile
    return profile.designation if profile else None


def _active_holders(designation_id, requester_id):
    return User.query.join(EmployeeProfile, EmployeeProfile.user_id == User.id).filter(
        User.is_active.is_(True),
        EmployeeProfile.designation_id == designation_id,
        User.id != requester_id,
    ).order_by(EmployeeProfile.full_name).all()


def _close_open_assignments(case):
    now = datetime.utcnow()
    for assignment in case.assignments:
        if assignment.status == "pending":
            assignment.status, assignment.acted_at = "superseded", now


def _assign_users(case, users, designation_id, assigned_by_id=None):
    if not users:
        raise ValueError("No active employee currently holds the selected designation.")
    for user in users:
        db.session.add(DesignationApprovalAssignment(
            case_id=case.id,
            assignee_id=user.id,
            designation_id=designation_id,
            assigned_by_id=assigned_by_id,
        ))
    case.current_designation_id = designation_id
    case.status = "pending"
    case.awaiting_response_from_id = None
    case.return_to_approver_id = None


def start_designation_approval(subject_type, subject_id, requester):
    """Route a new request to its named reporting officer."""
    profile = requester.employee_profile
    manager = profile.reporting_officer if profile else None
    if not manager or not manager.is_active:
        raise ValueError("A valid active reporting officer must be assigned before this request can be submitted.")
    if manager.id == requester.id:
        raise ValueError("A request cannot be routed to its creator.")
    existing = DesignationApprovalCase.query.filter_by(
        subject_type=subject_type, subject_id=subject_id,
    ).first()
    if existing:
        return existing
    designation = _designation_for(manager)
    case = DesignationApprovalCase(
        subject_type=subject_type,
        subject_id=subject_id,
        requester_id=requester.id,
        status="pending",
        current_designation_id=designation.id if designation else None,
    )
    db.session.add(case)
    db.session.flush()
    _assign_users(case, [manager], designation.id if designation else None)
    db.session.add(DesignationApprovalAction(
        case_id=case.id,
        actor_id=requester.id,
        action="submitted",
        to_designation_id=designation.id if designation else None,
        target_user_id=manager.id,
    ))
    return case


def pending_assignments_for(user):
    return DesignationApprovalAssignment.query.join(DesignationApprovalCase).filter(
        DesignationApprovalAssignment.assignee_id == user.id,
        DesignationApprovalAssignment.status == "pending",
        DesignationApprovalCase.status == "pending",
    ).order_by(DesignationApprovalAssignment.assigned_at.asc())


def case_for_subject(subject_type, subject_id):
    return DesignationApprovalCase.query.filter_by(
        subject_type=subject_type, subject_id=subject_id,
    ).first()


def _current_assignment(case, actor):
    assignment = DesignationApprovalAssignment.query.filter_by(
        case_id=case.id, assignee_id=actor.id, status="pending",
    ).first()
    if not assignment or case.status != "pending":
        raise PermissionError("This request is no longer assigned to you.")
    return assignment


def _previous_assignee(case, actor_id):
    return DesignationApprovalAssignment.query.filter(
        DesignationApprovalAssignment.case_id == case.id,
        DesignationApprovalAssignment.assignee_id != actor_id,
        DesignationApprovalAssignment.status.in_(("completed", "superseded")),
    ).order_by(DesignationApprovalAssignment.acted_at.desc(), DesignationApprovalAssignment.id.desc()).first()


def act_on_approval_case(case, actor, action, comment=None, designation_id=None):
    """Apply a terminal decision, referral, or return with an auditable action."""
    if action not in {"approved", "rejected", "refer", "return_to_requester", "return_to_previous"}:
        raise ValueError("Unsupported approval action.")
    if action in {"refer", "return_to_requester", "return_to_previous"} and not (comment or "").strip():
        raise ValueError("A comment is required when returning or referring a request.")
    assignment = _current_assignment(case, actor)
    now = datetime.utcnow()
    actor_designation = _designation_for(actor)
    assignment.status, assignment.acted_at = "completed", now

    if action == "refer":
        designation = db.session.get(Designation, designation_id)
        if not designation or not designation.is_active:
            raise ValueError("Choose an active designation for referral.")
        holders = _active_holders(designation.id, case.requester_id)
        _close_open_assignments(case)
        _assign_users(case, holders, designation.id, actor.id)
        event_action, target_user_id = "referred", None
    elif action == "return_to_previous":
        previous = _previous_assignee(case, actor.id)
        if previous is None or not previous.assignee.is_active:
            raise ValueError("There is no active previous approver to return this request to.")
        _close_open_assignments(case)
        _assign_users(case, [previous.assignee], previous.designation_id, actor.id)
        event_action, designation_id, target_user_id = "returned_to_previous", previous.designation_id, previous.assignee_id
    elif action == "return_to_requester":
        _close_open_assignments(case)
        case.status = "more_information_required"
        case.current_designation_id = None
        case.awaiting_response_from_id = case.requester_id
        case.return_to_approver_id = actor.id
        event_action, target_user_id = "returned_to_requester", case.requester_id
    else:
        _close_open_assignments(case)
        case.status, case.completed_at = action, now
        case.current_designation_id = None
        event_action, target_user_id = action, None

    db.session.add(DesignationApprovalAction(
        case_id=case.id,
        actor_id=actor.id,
        action=event_action,
        comment=(comment or "").strip() or None,
        from_designation_id=actor_designation.id if actor_designation else None,
        to_designation_id=designation_id,
        target_user_id=target_user_id,
    ))
    return case.status


def resubmit_designation_approval(case, requester):
    """Return an information-requested case to the approver who requested it."""
    if (
        not case
        or case.status != "more_information_required"
        or case.requester_id != requester.id
        or not case.return_to_approver_id
    ):
        return False
    approver = db.session.get(User, case.return_to_approver_id)
    if not approver or not approver.is_active:
        raise ValueError("The previous approver is no longer active. Ask HR to route this request.")
    designation = _designation_for(approver)
    _assign_users(case, [approver], designation.id if designation else None, requester.id)
    db.session.add(DesignationApprovalAction(
        case_id=case.id,
        actor_id=requester.id,
        action="resubmitted",
        to_designation_id=designation.id if designation else None,
        target_user_id=approver.id,
    ))
    return True
