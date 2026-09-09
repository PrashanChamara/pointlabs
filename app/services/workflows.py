"""Configuration-driven approval routing with preserved, auditable decisions."""
from datetime import datetime

from app.extensions import db
from app.models.hr import ApprovalDecision, ApprovalInstance, ApprovalWorkflow
from app.models.user import EmployeeProfile, User


def active_workflow(applies_to, request_type=None):
    """Prefer a service-specific route; otherwise use the active route for the event."""
    if request_type and request_type.workflow_id:
        candidate = db.session.get(ApprovalWorkflow, request_type.workflow_id)
        if candidate and candidate.is_active:
            return candidate
    return ApprovalWorkflow.query.filter_by(applies_to=applies_to, is_active=True).order_by(ApprovalWorkflow.id).first()


def _approvers(step, requester):
    if step.approver_kind == "direct_manager":
        profile = requester.employee_profile
        return [profile.reporting_officer] if profile and profile.reporting_officer and profile.reporting_officer.is_active else []
    if step.approver_kind == "named_user":
        user = step.approver_user
        return [user] if user and user.is_active else []
    if step.approver_kind == "hr_access":
        return [user for user in User.query.filter_by(is_active=True).all() if user.has_hr_access]
    if step.approver_kind == "access_role" and step.access_role_id:
        return User.query.filter_by(access_role_id=step.access_role_id, is_active=True).all()
    if step.designation_id:
        return User.query.join(EmployeeProfile, EmployeeProfile.user_id == User.id).filter(
            User.is_active.is_(True), EmployeeProfile.designation_id == step.designation_id
        ).all()
    return []


def start_workflow(workflow, subject_type, subject_id, requester):
    """Create the first actionable stage. Empty stages are rejected rather than silently bypassed."""
    if not workflow or not workflow.steps:
        return None
    instance = ApprovalInstance(
        workflow_id=workflow.id, subject_type=subject_type, subject_id=subject_id,
        requester_id=requester.id, current_step_order=workflow.steps[0].step_order,
    )
    db.session.add(instance)
    db.session.flush()
    _create_step_decisions(instance, workflow.steps[0], requester)
    return instance


def _create_step_decisions(instance, step, requester):
    candidates = [user for user in _approvers(step, requester) if user.id != requester.id]
    if not candidates:
        raise ValueError(f"The approval step {step.step_order} has no active eligible approvers.")
    for user in candidates:
        db.session.add(ApprovalDecision(
            approval_instance_id=instance.id, workflow_step_id=step.id, approver_id=user.id,
        ))


def pending_decisions_for(user):
    return ApprovalDecision.query.join(ApprovalInstance).filter(
        ApprovalDecision.approver_id == user.id,
        ApprovalDecision.status == "pending",
        ApprovalInstance.status == "pending",
    ).order_by(ApprovalInstance.created_at.asc())


def decide(decision, actor, action, comment=None):
    """Apply one action and atomically advance an any/all sequential workflow.

    Returns ``(instance, terminal_status)``; terminal status is None until the last step.
    """
    if decision.approver_id != actor.id or decision.status != "pending":
        raise PermissionError("This approval is no longer available to you.")
    if action not in {"approved", "rejected", "more_information_required"}:
        raise ValueError("Unsupported approval action.")
    instance = decision.instance
    if instance.status != "pending":
        raise ValueError("This workflow is no longer awaiting a decision.")
    decision.status, decision.comment, decision.acted_at = action, (comment or None), datetime.utcnow()
    if action in {"rejected", "more_information_required"}:
        instance.status = action
        instance.completed_at = datetime.utcnow()
        return instance, action

    peers = ApprovalDecision.query.filter_by(
        approval_instance_id=instance.id, workflow_step_id=decision.workflow_step_id,
    ).all()
    step = decision.step
    approved = [item for item in peers if item.status == "approved"]
    if step.approval_mode == "all" and len(approved) < len(peers):
        return instance, None
    for peer in peers:
        if peer.id != decision.id and peer.status == "pending":
            peer.status, peer.acted_at = "skipped", datetime.utcnow()
    next_step = next((item for item in instance.workflow.steps if item.step_order > step.step_order), None)
    if next_step:
        instance.current_step_order = next_step.step_order
        _create_step_decisions(instance, next_step, instance.requester)
        return instance, None
    instance.status, instance.completed_at = "approved", datetime.utcnow()
    return instance, "approved"


def resubmit_after_more_information(instance):
    """Return the recorded stage to its approver without creating a duplicate route.

    The request's AuditEvent/activity stream retains the prior comment; this keeps one
    traceable workflow instance per business request while allowing the employee reply.
    """
    if instance.status != "more_information_required":
        return False
    decisions = ApprovalDecision.query.filter_by(approval_instance_id=instance.id, status="more_information_required").all()
    if not decisions:
        return False
    for decision in decisions:
        decision.status, decision.acted_at = "pending", None
    instance.status, instance.completed_at = "pending", None
    instance.current_step_order = decisions[0].step.step_order
    return True
