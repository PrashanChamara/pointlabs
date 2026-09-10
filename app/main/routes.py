from datetime import date, datetime, timedelta
from io import BytesIO, StringIO
from pathlib import Path
import csv
from decimal import Decimal, InvalidOperation

from flask import abort, current_app, flash, redirect, render_template, request, send_file, send_from_directory, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from app.extensions import db
from app.main import bp
from app.models.hr import (
    AttendanceRecord, AuditEvent, CompensationRecord, DirectMessage, EmployeeDocument, LeaveBalance, LeaveRequest,
    LeaveType, Notification, OtherRequest, OtherRequestActivity, OtherRequestAttachment,
    Payslip, PublicHoliday, RequestType, ApprovalWorkflow, ApprovalWorkflowStep,
    ApprovalDecision, ApprovalInstance, WorkspaceNote, WorkspaceTask,
)
from app.models.organization import AccessRole, Department, Designation, Entity, Location
from app.models.user import EmployeeProfile, User
from app.services.email import (
    send_leave_confirmation_email, send_leave_status_email, send_message_email,
    send_notice_email, send_payslip_email,
)
from app.services.files import store_uploaded_file
from app.services.hr import (
    adjust_leave_balance, apply_approved_leave_balance, deactivate_resigned_employees,
    get_or_create_leave_balance, leave_days_for_profile, restore_cancelled_leave_balance,
    would_create_reporting_cycle,
)
from app.services.pdf import (
    generate_leave_confirmation_pdf, generate_payslip_pdf, leave_confirmation_pdf_path,
    payslip_pdf_path,
)
from app.services.workflows import active_workflow, decide, pending_decisions_for, resubmit_after_more_information, start_workflow


def admin_only():
    return None if current_user.has_hr_access else ("Forbidden", 403)


def configuration_only():
    return None if current_user.is_administrator or bool(current_user.access_role and current_user.access_role.can_manage_configuration) else ("Forbidden", 403)


def _parse_iso_date(field_name):
    value = request.form.get(field_name, "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{field_name.replace('_', ' ').title()} must be a valid date.")


def _valid_work_email(email):
    return not email or ("@" in email and email.rsplit("@", 1)[1].strip())


def _active_managers(exclude_user_id=None):
    query = EmployeeProfile.query.join(User, EmployeeProfile.user_id == User.id).filter(User.is_active.is_(True))
    if exclude_user_id:
        query = query.filter(EmployeeProfile.user_id != exclude_user_id)
    return query.order_by(EmployeeProfile.full_name).all()


def _hr_users():
    """Access roles are evaluated in Python so the same policy applies everywhere."""
    return [user for user in User.query.filter_by(is_active=True).all() if user.has_hr_access]


def _set_profile_from_form(profile):
    """Apply the HR-only profile form after validating dates and reporting hierarchy."""
    joining_date = _parse_iso_date("date_of_joining")
    probation_end_date = _parse_iso_date("probation_end_date")
    resignation_date = _parse_iso_date("resignation_date")
    if joining_date and resignation_date and resignation_date < joining_date:
        raise ValueError("Resignation date cannot be earlier than date of joining.")
    manager_id = request.form.get("reporting_officer_id", type=int)
    if manager_id and would_create_reporting_cycle(profile.user_id, manager_id):
        raise ValueError("The selected reporting manager would create a reporting cycle.")

    text_fields = (
        "employee_code", "full_name", "preferred_name", "phone", "current_address",
        "permanent_address", "home_country_contact_number", "personal_email", "employment_type",
        "gender", "nationality", "marital_status", "national_identity_card_number",
        "emirates_id_number", "passport_number", "emergency_contact_name",
        "emergency_contact_number", "emergency_contact_relationship", "account_holder_name",
        "bank_name", "branch_name", "bank_account_number", "swift_code", "ifsc_code",
        "bank_address", "bank_currency",
    )
    for field in text_fields:
        if field in request.form:
            setattr(profile, field, request.form.get(field, "").strip() or None)
    profile.address = profile.current_address  # Preserve compatibility with the original profile field.
    profile.date_of_birth = _parse_iso_date("date_of_birth")
    profile.date_of_joining = joining_date
    profile.probation_end_date = probation_end_date
    profile.resignation_date = resignation_date
    profile.emirates_id_expiry_date = _parse_iso_date("emirates_id_expiry_date")
    profile.passport_expiry_date = _parse_iso_date("passport_expiry_date")
    profile.entity_id = request.form.get("entity_id", type=int)
    profile.location_id = request.form.get("location_id", type=int)
    profile.department_id = request.form.get("department_id", type=int)
    profile.designation_id = request.form.get("designation_id", type=int)
    profile.reporting_officer_id = manager_id
    profile.employment_status = request.form.get("employment_status", "active")
    if profile.resignation_date and profile.resignation_date <= date.today():
        profile.employment_status = "resigned"
        profile.user.is_active = False


def _store_employee_documents(owner, files, category="Employee record"):
    for file in files:
        if not file or not file.filename:
            continue
        stored_path, mime_type, size = store_uploaded_file(file, f"employee-{owner.id}")
        db.session.add(EmployeeDocument(
            user_id=owner.id,
            category=category,
            filename=file.filename,
            stored_path=stored_path,
            mime_type=mime_type,
            file_size=size,
            uploaded_by_id=current_user.id,
        ))


def greeting_for_hour(hour):
    if 5 <= hour < 12:
        return "Good morning"
    if 12 <= hour < 18:
        return "Good afternoon"
    return "Good evening"


def next_birthday(date_of_birth, today):
    """Return the next birthday, treating 29 February as 28 February in non-leap years."""
    def in_year(year):
        try:
            return date_of_birth.replace(year=year)
        except ValueError:
            return date(year, 2, 28)

    birthday = in_year(today.year)
    return birthday if birthday >= today else in_year(today.year + 1)


def display_name(user):
    return user.employee_profile.full_name if user.employee_profile else user.username


def ensure_profile(user):
    """Repair historic test users created before profiles became mandatory."""
    if user.employee_profile is None:
        db.session.add(EmployeeProfile(
            user_id=user.id,
            employee_code="PL-ADMIN-001" if user.is_administrator else None,
            full_name="Pointlabs Administrator" if user.is_administrator else user.username,
        ))
        db.session.commit()
    return user.employee_profile


@bp.get("/")
@login_required
def dashboard():
    pending = LeaveRequest.query.filter(LeaveRequest.status.in_(("submitted", "returned", "cancellation_requested"))).count() if current_user.can_approve_leave else 0
    today = LeaveRequest.query.filter(LeaveRequest.status == "approved", LeaveRequest.start_date <= date.today(), LeaveRequest.end_date >= date.today()).all()
    notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).order_by(Notification.created_at.desc()).all()
    active_request_statuses = ("submitted", "resubmitted", "more_information_required", "in_review", "in_progress")
    request_query = OtherRequest.query.filter(OtherRequest.status.in_(active_request_statuses))
    active_requests = request_query.count() if current_user.has_hr_access else request_query.filter_by(user_id=current_user.id).count()
    focus_tasks = WorkspaceTask.query.filter_by(user_id=current_user.id, completed_at=None).order_by(
        WorkspaceTask.due_at.is_(None), WorkspaceTask.due_at, WorkspaceTask.created_at.desc(),
    ).limit(4).all()
    attendance_today = AttendanceRecord.query.filter_by(user_id=current_user.id, work_date=date.today()).first()
    upcoming_birthdays = []
    if current_user.has_hr_access:
        for profile in EmployeeProfile.query.join(User, EmployeeProfile.user_id == User.id).filter(User.is_active.is_(True), EmployeeProfile.date_of_birth.isnot(None)).all():
            birthday = next_birthday(profile.date_of_birth, date.today())
            if birthday <= date.today() + timedelta(days=45):
                upcoming_birthdays.append((birthday, profile))
        upcoming_birthdays.sort(key=lambda item: item[0])
    return render_template(
        "dashboard.html", pending=pending, today=today, notifications=notifications,
        unread_messages=DirectMessage.query.filter_by(recipient_id=current_user.id, is_read=False).count(),
        greeting=greeting_for_hour(datetime.now().hour),
        people_count=EmployeeProfile.query.join(User, EmployeeProfile.user_id == User.id).filter(User.is_active.is_(True)).count(),
        active_requests=active_requests, focus_tasks=focus_tasks, attendance_today=attendance_today,
        upcoming_birthdays=upcoming_birthdays[:4],
    )


@bp.route("/leave", methods=["GET", "POST"])
@login_required
def leave():
    if request.method == "POST":
        try:
            start, end = date.fromisoformat(request.form["start_date"]), date.fromisoformat(request.form["end_date"])
        except (KeyError, ValueError):
            flash("Choose valid leave dates.")
            return redirect(url_for("main.leave"))
        if end < start:
            flash("End date must be on or after the start date.")
            return redirect(url_for("main.leave"))
        leave_type = db.session.get(LeaveType, request.form.get("leave_type", type=int))
        profile = ensure_profile(current_user)
        if leave_type is None or not leave_type.is_active:
            flash("Choose an active leave type.")
            return redirect(url_for("main.leave"))
        if profile.resignation_date and date.today() <= profile.resignation_date:
            flash("Leave cannot be requested during a notice period.")
            return redirect(url_for("main.leave"))
        if leave_type.code == "ANNUAL" and profile.probation_end_date and start < profile.probation_end_date:
            flash("Annual leave is unavailable until the recorded probation end date.")
            return redirect(url_for("main.leave"))
        days = leave_days_for_profile(profile, start, end)
        if days <= 0:
            flash("The selected period contains no working days after weekends and public holidays.")
            return redirect(url_for("main.leave"))
        balance = get_or_create_leave_balance(current_user, leave_type, start.year)
        if leave_type.code != "LWP" and balance.available_days < days:
            lwp_type = LeaveType.query.filter_by(code="LWP", is_active=True).first()
            if lwp_type:
                leave_type = lwp_type
                flash("The requested days exceed the available balance and were recorded as Leave Without Pay for review.")
        item = LeaveRequest(user_id=current_user.id, leave_type_id=leave_type.id, start_date=start, end_date=end, days=days, reason=request.form.get("reason", "").strip() or None)
        db.session.add(item)
        db.session.flush()
        try:
            instance = start_workflow(active_workflow("leave"), "leave", item.id, current_user)
        except ValueError as error:
            db.session.rollback()
            flash(str(error))
            return redirect(url_for("main.leave"))
        if instance:
            for decision in instance.decisions:
                db.session.add(Notification(user_id=decision.approver_id, message=f"{display_name(current_user)} submitted a {leave_type.name} request for your approval."))
        manager = profile.reporting_officer
        if not instance and manager and manager.is_active:
            db.session.add(Notification(user_id=manager.id, message=f"{display_name(current_user)} submitted a {leave_type.name} request for review."))
        db.session.commit()
        flash("Leave request submitted for review.")
        return redirect(url_for("main.leave"))
    balances = [get_or_create_leave_balance(current_user, leave_type) for leave_type in LeaveType.query.filter_by(is_active=True).all()]
    db.session.commit()
    return render_template("leave.html", requests=LeaveRequest.query.filter_by(user_id=current_user.id).order_by(LeaveRequest.created_at.desc()).all(), leave_types=LeaveType.query.filter_by(is_active=True).all(), balances=balances)


@bp.post("/leave/<int:request_id>/edit")
@login_required
def edit_leave(request_id):
    """Allow an employee to correct a request only before a final decision."""
    item = db.get_or_404(LeaveRequest, request_id)
    if item.user_id != current_user.id:
        return "Forbidden", 403
    if item.status not in {"submitted", "returned"}:
        return "This leave request can no longer be edited", 409
    try:
        start = date.fromisoformat(request.form.get("start_date", ""))
        end = date.fromisoformat(request.form.get("end_date", ""))
    except ValueError:
        flash("Choose valid leave dates.")
        return redirect(url_for("main.leave"))
    if end < start:
        flash("End date must be on or after the start date.")
        return redirect(url_for("main.leave"))
    leave_type = db.session.get(LeaveType, request.form.get("leave_type", type=int))
    if leave_type is None or not leave_type.is_active:
        flash("Choose an active leave type.")
        return redirect(url_for("main.leave"))
    profile = ensure_profile(current_user)
    if profile.resignation_date and date.today() <= profile.resignation_date:
        flash("Leave cannot be requested during a notice period.")
        return redirect(url_for("main.leave"))
    if leave_type.code == "ANNUAL" and profile.probation_end_date and start < profile.probation_end_date:
        flash("Annual leave is unavailable until the recorded probation end date.")
        return redirect(url_for("main.leave"))
    days = leave_days_for_profile(profile, start, end)
    if days <= 0:
        flash("The selected period contains no working days after weekends and public holidays.")
        return redirect(url_for("main.leave"))
    balance = get_or_create_leave_balance(current_user, leave_type, start.year)
    if leave_type.code != "LWP" and balance.available_days < days:
        lwp_type = LeaveType.query.filter_by(code="LWP", is_active=True).first()
        if lwp_type:
            leave_type = lwp_type
            flash("The revised days exceed the available balance and were recorded as Leave Without Pay for review.")
    item.leave_type_id = leave_type.id
    item.start_date, item.end_date, item.days = start, end, days
    item.reason = request.form.get("reason", "").strip() or None
    item.status, item.reviewer_comment = "submitted", None
    instance = ApprovalInstance.query.filter_by(subject_type="leave", subject_id=item.id).first()
    if instance and resubmit_after_more_information(instance):
        for decision in instance.decisions:
            if decision.status == "pending":
                db.session.add(Notification(user_id=decision.approver_id, message=f"{display_name(current_user)} supplied the requested leave information."))
    db.session.add(AuditEvent(actor_id=current_user.id, entity_type="leave_request", entity_id=item.id, action="employee_edited", summary="Employee updated a pending leave request before final review."))
    manager = profile.reporting_officer
    if manager and manager.is_active:
        db.session.add(Notification(user_id=manager.id, message=f"{display_name(current_user)} updated a {leave_type.name} request for review."))
    db.session.commit()
    flash("Leave request updated and returned to your reporting manager for review.")
    return redirect(url_for("main.leave"))


@bp.post("/leave/<int:request_id>/<action>")
@login_required
def review_leave(request_id, action):
    item = db.get_or_404(LeaveRequest, request_id)
    if ApprovalInstance.query.filter_by(subject_type="leave", subject_id=item.id, status="pending").first():
        return "This request must be decided through its configured approval workflow", 409
    permitted = current_user.has_hr_access or (item.user.employee_profile and item.user.employee_profile.reporting_officer_id == current_user.id)
    if not permitted:
        return "Forbidden", 403
    if action == "approve-cancellation":
        if item.status != "cancellation_requested":
            return "Invalid leave cancellation state", 409
        item.status, item.cancelled_at, item.cancellation_reviewer_id = "cancelled", datetime.utcnow(), current_user.id
        restore_cancelled_leave_balance(item)
        db.session.add(AuditEvent(actor_id=current_user.id, entity_type="leave_request", entity_id=item.id, action="cancellation_approved", summary="Approved leave cancellation and restored the applicable balance."))
        db.session.add(Notification(user_id=item.user_id, message=f"Your cancellation request for {item.leave_type.name} has been approved."))
        db.session.commit()
        flash("Leave cancellation approved and balance restored.")
        return redirect(url_for("main.approvals"))
    if action == "reject-cancellation":
        if item.status != "cancellation_requested":
            return "Invalid leave cancellation state", 409
        item.status, item.cancellation_reviewer_id = "approved", current_user.id
        db.session.add(AuditEvent(actor_id=current_user.id, entity_type="leave_request", entity_id=item.id, action="cancellation_declined", summary="Declined leave cancellation; the approved leave remains in effect."))
        db.session.add(Notification(user_id=item.user_id, message=f"Your cancellation request for {item.leave_type.name} was declined."))
        db.session.commit()
        flash("Leave cancellation declined.")
        return redirect(url_for("main.approvals"))
    if item.status not in {"submitted", "returned"}:
        return "This leave request is no longer awaiting a decision", 409
    result = {"approve": "approved", "reject": "rejected", "return": "returned"}.get(action)
    if result is None:
        return "Unknown action", 400
    item.status, item.reviewer_comment = result, request.form.get("comment", "").strip() or None
    item.approver_id = current_user.id
    if result == "approved":
        apply_approved_leave_balance(item)
        db.session.flush()
        try:
            stored_path, filename = generate_leave_confirmation_pdf(item)
        except Exception:
            current_app.logger.exception("Leave confirmation PDF generation failed for leave request %s", item.id)
            item.confirmation_generation_error = "The leave confirmation document could not be generated."
        else:
            item.confirmation_stored_path = stored_path
            item.confirmation_filename = filename
            item.confirmation_generated_at = datetime.utcnow()
            item.confirmation_generation_error = None
    employee_name = display_name(item.user)
    db.session.add(AuditEvent(
        actor_id=current_user.id, entity_type="leave_request", entity_id=item.id,
        action=result, summary=f"{result.title()} {item.leave_type.name} leave request for {employee_name}.",
    ))
    message = f"{employee_name}'s {item.leave_type.name} leave request was {result}."
    db.session.add(Notification(user_id=item.user_id, message=message))
    db.session.commit()
    if result == "approved" and item.confirmation_stored_path and item.user.email:
        confirmation_path = leave_confirmation_pdf_path(item.confirmation_stored_path)
        if confirmation_path.is_file() and send_leave_confirmation_email(
            item.user.email,
            employee_name,
            item.leave_type.name,
            f"{item.start_date:%d %b %Y} – {item.end_date:%d %b %Y}",
            confirmation_path,
            item.confirmation_filename,
        ):
            item.confirmation_emailed_at = datetime.utcnow()
            db.session.commit()
    elif result != "approved":
        for address in {current_app.config.get("SMTP_FROM"), item.user.email} - {None, ""}:
            send_leave_status_email(address, employee_name, item.leave_type.name, result, item.reviewer_comment)
    if result == "approved" and item.confirmation_generation_error:
        flash("Leave approved, but the confirmation PDF could not be generated. HR can retry after resolving the server issue.")
    else:
        flash(f"Leave request {result}.")
    return redirect(url_for("main.approvals"))


@bp.post("/leave/<int:request_id>/cancel")
@login_required
def cancel_leave(request_id):
    item = db.get_or_404(LeaveRequest, request_id)
    if item.user_id != current_user.id:
        return "Forbidden", 403
    if item.status in {"submitted", "returned"}:
        item.status, item.cancelled_at = "cancelled", datetime.utcnow()
        db.session.add(AuditEvent(actor_id=current_user.id, entity_type="leave_request", entity_id=item.id, action="cancelled", summary="Employee cancelled a pending leave request."))
        db.session.commit()
        flash("Pending leave request cancelled.")
        return redirect(url_for("main.leave"))
    if item.status != "approved":
        return "This leave request cannot be cancelled", 409
    item.status = "cancellation_requested"
    item.cancellation_requested_at = datetime.utcnow()
    item.cancellation_reason = request.form.get("reason", "").strip() or None
    db.session.add(AuditEvent(actor_id=current_user.id, entity_type="leave_request", entity_id=item.id, action="cancellation_requested", summary="Employee requested cancellation of approved leave."))
    manager = item.user.employee_profile.reporting_officer if item.user.employee_profile else None
    if manager and manager.is_active:
        db.session.add(Notification(user_id=manager.id, message=f"{display_name(current_user)} requested cancellation of {item.leave_type.name}."))
    db.session.commit()
    flash("Cancellation request submitted to your reporting manager.")
    return redirect(url_for("main.leave"))


@bp.get("/leave/<int:request_id>/confirmation.pdf")
@login_required
def download_leave_confirmation(request_id):
    item = db.get_or_404(LeaveRequest, request_id)
    is_reporting_manager = bool(item.user.employee_profile and item.user.employee_profile.reporting_officer_id == current_user.id)
    if not (current_user.has_hr_access or item.user_id == current_user.id or is_reporting_manager):
        return "Forbidden", 403
    if not item.confirmation_stored_path:
        abort(404)
    path = leave_confirmation_pdf_path(item.confirmation_stored_path)
    if not path.is_file():
        current_app.logger.error("Leave confirmation file is missing for request %s", item.id)
        abort(404)
    return send_from_directory(path.parent, path.name, as_attachment=True, download_name=item.confirmation_filename)


def _leave_review_scope():
    """Return leave requests this user is authorised to decide."""
    query = LeaveRequest.query.order_by(LeaveRequest.created_at.asc())
    if current_user.has_hr_access:
        return query
    return query.join(User, LeaveRequest.user_id == User.id).join(
        EmployeeProfile, EmployeeProfile.user_id == User.id,
    ).filter(EmployeeProfile.reporting_officer_id == current_user.id)


@bp.get("/approvals")
@login_required
def approvals():
    """One operational inbox for manager leave and HR service decisions."""
    configured_decisions = pending_decisions_for(current_user).all()
    if not current_user.can_approve_leave and not configured_decisions:
        return "Forbidden", 403
    leave_items = _leave_review_scope().filter(
        LeaveRequest.status.in_(("submitted", "returned", "cancellation_requested")),
    ).all()
    leave_items = [item for item in leave_items if not ApprovalInstance.query.filter_by(subject_type="leave", subject_id=item.id, status="pending").first()]
    request_items = []
    if current_user.has_hr_access:
        request_items = OtherRequest.query.filter(
            OtherRequest.status.in_(("submitted", "resubmitted", "more_information_required", "in_review", "in_progress")),
        ).order_by(OtherRequest.updated_at.asc()).all()
        request_items = [item for item in request_items if not ApprovalInstance.query.filter_by(subject_type="other_request", subject_id=item.id, status="pending").first()]
    return render_template("approvals.html", leave_items=leave_items, request_items=request_items, configured_decisions=configured_decisions)


@bp.post("/approvals/decision/<int:decision_id>/<action>")
@login_required
def approval_decision(decision_id, action):
    decision = db.get_or_404(ApprovalDecision, decision_id)
    try:
        instance, terminal = decide(decision, current_user, action, request.form.get("comment", "").strip())
    except PermissionError:
        return "Forbidden", 403
    except ValueError as error:
        return str(error), 409
    subject = db.session.get(LeaveRequest if instance.subject_type == "leave" else OtherRequest, instance.subject_id)
    if subject is None:
        return "Approval subject no longer exists", 410
    if terminal == "approved":
        if instance.subject_type == "leave":
            subject.status, subject.approver_id = "approved", current_user.id
            apply_approved_leave_balance(subject)
            db.session.flush()
            try:
                stored_path, filename = generate_leave_confirmation_pdf(subject)
                subject.confirmation_stored_path, subject.confirmation_filename = stored_path, filename
                subject.confirmation_generated_at, subject.confirmation_generation_error = datetime.utcnow(), None
            except Exception:
                current_app.logger.exception("Leave confirmation PDF generation failed for leave request %s", subject.id)
                subject.confirmation_generation_error = "The leave confirmation document could not be generated."
            db.session.add(Notification(user_id=subject.user_id, message="Your leave request has been approved."))
        else:
            subject.status = "in_review"
            db.session.add(Notification(user_id=subject.user_id, message="Your HR request has passed its approval stage and is now in review."))
    elif terminal == "rejected":
        subject.status = "rejected"
        db.session.add(Notification(user_id=subject.user_id, message="Your request was declined. Please review the approver's comment."))
    elif terminal == "more_information_required":
        subject.status = "returned" if instance.subject_type == "leave" else "more_information_required"
        db.session.add(Notification(user_id=subject.user_id, message="More information is required before your request can proceed."))
    db.session.add(AuditEvent(actor_id=current_user.id, entity_type=instance.subject_type, entity_id=subject.id, action=f"workflow_{action}", summary=f"Workflow decision recorded in {instance.workflow.name}."))
    db.session.commit()
    flash("Approval decision recorded." if terminal else "Decision recorded; the next configured approval stage is now active.")
    return redirect(url_for("main.approvals"))


@bp.route("/admin/leave-balances", methods=["GET", "POST"])
@login_required
def leave_balances():
    denied = admin_only()
    if denied:
        return denied
    if request.method == "POST":
        user = db.session.get(User, request.form.get("user_id", type=int))
        leave_type = db.session.get(LeaveType, request.form.get("leave_type_id", type=int))
        year = request.form.get("calendar_year", type=int) or date.today().year
        reason = request.form.get("reason", "").strip()
        try:
            days = float(request.form.get("days", ""))
        except ValueError:
            days = None
        if user is None or leave_type is None or not reason or days is None or not -366 <= days <= 366:
            flash("Choose an employee and leave type, enter a reasonable adjustment, and explain why it is needed.")
            return redirect(url_for("main.leave_balances", year=year))
        balance = get_or_create_leave_balance(user, leave_type, year)
        db.session.flush()
        adjust_leave_balance(balance, days, reason, actor=current_user)
        db.session.add(AuditEvent(
            actor_id=current_user.id, entity_type="leave_balance", entity_id=balance.id,
            action="adjusted", summary=f"Adjusted {leave_type.name} by {days:+.1f} days for {year}: {reason}",
        ))
        db.session.commit()
        flash("Leave balance adjustment recorded. The adjustment history has been retained.")
        return redirect(url_for("main.leave_balances", year=year, user_id=user.id))

    year = request.args.get("year", date.today().year, type=int)
    selected_user_id = request.args.get("user_id", type=int)
    employees = EmployeeProfile.query.join(User, EmployeeProfile.user_id == User.id).filter(User.is_active.is_(True)).order_by(EmployeeProfile.full_name).all()
    leave_types = LeaveType.query.filter_by(is_active=True).order_by(LeaveType.name).all()
    selected_user = db.session.get(User, selected_user_id) if selected_user_id else None
    if selected_user and not selected_user.employee_profile:
        selected_user = None
    target_users = [selected_user] if selected_user else [profile.user for profile in employees]
    balances = []
    for user in target_users:
        if user is None:
            continue
        for leave_type in leave_types:
            balances.append(get_or_create_leave_balance(user, leave_type, year))
    db.session.commit()
    return render_template(
        "leave_balances.html", balances=balances, employees=employees, leave_types=leave_types,
        year=year, selected_user=selected_user,
    )


@bp.get("/admin/employees")
@login_required
def employees():
    denied = admin_only()
    if denied:
        return denied
    deactivate_resigned_employees()
    q = request.args.get("q", "").strip()
    designation_id = request.args.get("designation_id", type=int)
    department_id = request.args.get("department_id", type=int)
    location_id = request.args.get("location_id", type=int)
    status = request.args.get("status", "active")
    page = max(1, request.args.get("page", 1, type=int))
    query = EmployeeProfile.query.join(User, EmployeeProfile.user_id == User.id).order_by(EmployeeProfile.full_name)
    if q:
        query = query.filter(or_(EmployeeProfile.full_name.ilike(f"%{q}%"), EmployeeProfile.employee_code.ilike(f"%{q}%"), User.email.ilike(f"%{q}%")))
    if designation_id:
        query = query.filter(EmployeeProfile.designation_id == designation_id)
    if department_id:
        query = query.filter(EmployeeProfile.department_id == department_id)
    if location_id:
        query = query.filter(EmployeeProfile.location_id == location_id)
    if status == "active":
        query = query.filter(User.is_active.is_(True))
    elif status == "resigned":
        query = query.filter(EmployeeProfile.employment_status == "resigned")
    employees_page = query.paginate(page=page, per_page=10, error_out=False)
    return render_template(
        "employees.html",
        employees=employees_page,
        designations=Designation.query.order_by(Designation.name).all(),
        departments=Department.query.order_by(Department.name).all(),
        locations=Location.query.order_by(Location.name).all(),
        selected_designation_id=designation_id,
        selected_department_id=department_id,
        selected_location_id=location_id,
        selected_status=status,
    )


@bp.route("/admin/employees/new", methods=["GET", "POST"])
@login_required
def employee_new():
    denied = admin_only()
    if denied:
        return denied
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower() or None
        if not username or not request.form.get("full_name", "").strip():
            flash("Full name and user ID are required.")
            return redirect(url_for("main.employee_new"))
        if not _valid_work_email(email):
            flash("Enter a valid work email address.")
            return redirect(url_for("main.employee_new"))
        if User.query.filter_by(username=username).first() or (email and User.query.filter_by(email=email).first()):
            flash("The user ID or work email address is already in use.")
            return redirect(url_for("main.employee_new"))
        employee_code = request.form.get("employee_code", "").strip() or None
        if employee_code and EmployeeProfile.query.filter_by(employee_code=employee_code).first():
            flash("That employee code is already in use.")
            return redirect(url_for("main.employee_new"))
        # A designation is a job title. Access rights are managed separately on edit
        # by an administrator; reporting-manager assignments drive leave approvals.
        user = User(username=username, email=email, access_role_id=request.form.get("access_role_id", type=int), must_change_password=True)
        user.set_password(request.form.get("password") or "ChangeMe123!")
        db.session.add(user)
        db.session.flush()
        profile = EmployeeProfile(user_id=user.id, full_name=request.form["full_name"].strip(), employee_code=employee_code)
        db.session.add(profile)
        try:
            _set_profile_from_form(profile)
            _store_employee_documents(user, request.files.getlist("documents"), request.form.get("document_category", "Employee record"))
            db.session.commit()
        except ValueError as error:
            db.session.rollback()
            flash(str(error))
            return redirect(url_for("main.employee_new"))
        flash("Employee account created. The employee must change their temporary password at first sign-in.")
        return redirect(url_for("main.employee_detail", user_id=user.id))
    return render_template("employee_form.html", employee=None, profile=None, **_employee_form_options())


def _employee_form_options(user_id=None):
    return {
        "designations": Designation.query.filter_by(is_active=True).order_by(Designation.name).all(),
        "departments": Department.query.filter_by(is_active=True).order_by(Department.name).all(),
        "locations": Location.query.filter_by(is_active=True).order_by(Location.name).all(),
        "entities": Entity.query.filter_by(is_active=True).order_by(Entity.name).all(),
        "managers": _active_managers(exclude_user_id=user_id),
        "access_roles": AccessRole.query.filter_by(is_active=True).order_by(AccessRole.name).all(),
    }


@bp.get("/admin/employees/<int:user_id>")
@login_required
def employee_detail(user_id):
    denied = admin_only()
    if denied:
        return denied
    employee = db.get_or_404(User, user_id)
    profile = ensure_profile(employee)
    return render_template("employee_detail.html", employee=employee, profile=profile, documents=EmployeeDocument.query.filter_by(user_id=user_id).order_by(EmployeeDocument.uploaded_at.desc()).all())


@bp.route("/admin/employees/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
def employee_edit(user_id):
    denied = admin_only()
    if denied:
        return denied
    employee = db.get_or_404(User, user_id)
    profile = ensure_profile(employee)
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower() or None
        conflicting = User.query.filter(User.email == email, User.id != employee.id).first() if email else None
        if conflicting or not _valid_work_email(email):
            flash("Enter a unique, valid work email address.")
            return redirect(url_for("main.employee_edit", user_id=user_id))
        employee.email = email
        # Keep administrative access intentional and distinct from designation.
        if current_user.is_administrator:
            employee.access_role_id = request.form.get("access_role_id", type=int)
        try:
            _set_profile_from_form(profile)
            _store_employee_documents(employee, request.files.getlist("documents"), request.form.get("document_category", "Employee record"))
            db.session.commit()
        except ValueError as error:
            db.session.rollback()
            flash(str(error))
            return redirect(url_for("main.employee_edit", user_id=user_id))
        flash("Employee record updated.")
        return redirect(url_for("main.employee_detail", user_id=user_id))
    return render_template("employee_form.html", employee=employee, profile=profile, **_employee_form_options(user_id=user_id))


@bp.post("/admin/employees/<int:user_id>/archive")
@login_required
def employee_archive(user_id):
    denied = admin_only()
    if denied:
        return denied
    if user_id == current_user.id:
        flash("You cannot archive your own account.")
        return redirect(url_for("main.employee_detail", user_id=user_id))
    employee = db.get_or_404(User, user_id)
    profile = ensure_profile(employee)
    employee.is_active = False
    profile.employment_status = "inactive"
    db.session.commit()
    flash("Employee access has been archived. Historical records remain available to HR.")
    return redirect(url_for("main.employees", status="all"))


@bp.get("/admin/employees/export.csv")
@login_required
def employee_export():
    denied = admin_only()
    if denied:
        return denied
    stream = StringIO(); writer = csv.writer(stream)
    writer.writerow(["Employee ID", "Name", "Email", "Designation", "Department", "Location", "Status"])
    for profile in EmployeeProfile.query.order_by(EmployeeProfile.full_name).all():
        writer.writerow([profile.employee_code or "", profile.full_name, profile.user.email or "", profile.designation.name if profile.designation else "", profile.department.name if profile.department else "", profile.location.name if profile.location else "", "Active" if profile.user.is_active else "Inactive"])
    return send_file(BytesIO(stream.getvalue().encode()), mimetype="text/csv", as_attachment=True, download_name="pointlabs-employees.csv")


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    profile = ensure_profile(current_user)
    if request.method == "POST":
        work_email = request.form.get("email", "").strip().lower() or None
        conflicting = User.query.filter(User.email == work_email, User.id != current_user.id).first() if work_email else None
        if conflicting or not _valid_work_email(work_email):
            flash("Enter a unique, valid work email address.")
            return redirect(url_for("main.profile"))
        safe_updates = {
            "preferred name": request.form.get("preferred_name", "").strip() or None,
            "phone": request.form.get("phone", "").strip() or None,
            "personal email": request.form.get("personal_email", "").strip() or None,
            "address": request.form.get("address", "").strip() or None,
            "work email": work_email,
        }
        previous = {
            "preferred name": profile.preferred_name, "phone": profile.phone,
            "personal email": profile.personal_email, "address": profile.address,
            "work email": current_user.email,
        }
        profile.preferred_name = safe_updates["preferred name"]
        profile.phone = safe_updates["phone"]
        profile.personal_email = safe_updates["personal email"]
        profile.address = safe_updates["address"]
        profile.current_address = profile.address
        current_user.email = work_email
        changed = [field for field, value in safe_updates.items() if value != previous[field]]
        if changed:
            db.session.add(AuditEvent(actor_id=current_user.id, entity_type="employee_profile", entity_id=profile.id, action="self_service_updated", summary=f"Employee updated own profile fields: {', '.join(changed)}."))
        db.session.commit()
        flash("Your profile has been updated.")
        return redirect(url_for("main.profile"))
    return render_template("profile.html", profile=profile)


@bp.route("/workspace", methods=["GET", "POST"])
@login_required
def workspace():
    """Personal task list and notes, with optional HR-published notices."""
    if request.method == "POST":
        action = request.form.get("action")
        if action == "task-create":
            title = request.form.get("title", "").strip()
            if not title or len(title) > 240:
                flash("Enter a task title of up to 240 characters.")
            else:
                due_value = request.form.get("due_at", "").strip()
                try:
                    due_at = datetime.fromisoformat(due_value) if due_value else None
                except ValueError:
                    flash("Choose a valid task reminder date and time.")
                    return redirect(url_for("main.workspace"))
                db.session.add(WorkspaceTask(user_id=current_user.id, title=title, due_at=due_at))
                db.session.commit(); flash("Task added to your focus list.")
        elif action in {"task-complete", "task-delete"}:
            task = db.session.get(WorkspaceTask, request.form.get("task_id", type=int))
            if task is None or task.user_id != current_user.id:
                return "Forbidden", 403
            if action == "task-complete":
                task.completed_at = None if task.completed_at else datetime.utcnow()
                db.session.commit(); flash("Task status updated.")
            else:
                db.session.delete(task); db.session.commit(); flash("Task removed.")
        elif action == "note-create":
            body = request.form.get("body", "").strip()
            if not body or len(body) > 600:
                flash("Enter a note of up to 600 characters.")
            else:
                is_global = bool(request.form.get("is_global")) and current_user.has_hr_access
                db.session.add(WorkspaceNote(user_id=current_user.id, body=body, color=request.form.get("color", "gold"), is_global=is_global, show_everywhere=bool(request.form.get("show_everywhere"))))
                db.session.commit(); flash("Sticky note saved.")
        elif action == "note-delete":
            note = db.session.get(WorkspaceNote, request.form.get("note_id", type=int))
            if note is None or not (note.user_id == current_user.id or current_user.has_hr_access and note.is_global):
                return "Forbidden", 403
            db.session.delete(note); db.session.commit(); flash("Sticky note removed.")
        else:
            return "Invalid workspace action", 400
        return redirect(url_for("main.workspace"))
    tasks = WorkspaceTask.query.filter_by(user_id=current_user.id).order_by(WorkspaceTask.completed_at.isnot(None), WorkspaceTask.due_at.is_(None), WorkspaceTask.due_at, WorkspaceTask.created_at.desc()).all()
    notes = WorkspaceNote.query.filter((WorkspaceNote.user_id == current_user.id) | (WorkspaceNote.is_global.is_(True))).order_by(WorkspaceNote.created_at.desc()).all()
    return render_template("workspace.html", tasks=tasks, notes=notes, now=datetime.utcnow())


@bp.route("/attendance", methods=["GET", "POST"])
@login_required
def attendance():
    today = date.today()
    record = AttendanceRecord.query.filter_by(user_id=current_user.id, work_date=today).first()
    if request.method == "POST":
        action = request.form.get("action")
        now = datetime.utcnow()
        if action == "check-in":
            if record:
                flash("You have already checked in today.")
            else:
                db.session.add(AttendanceRecord(user_id=current_user.id, work_date=today, checked_in_at=now, check_in_note=request.form.get("note", "").strip()[:500] or None))
                db.session.commit(); flash("Check-in recorded.")
        elif action == "check-out":
            if not record or record.checked_out_at:
                flash("There is no open attendance record to check out.")
            else:
                record.checked_out_at, record.check_out_note = now, request.form.get("note", "").strip()[:500] or None
                db.session.commit(); flash("Check-out recorded. Have a good evening.")
        else:
            return "Invalid attendance action", 400
        return redirect(url_for("main.attendance"))
    history = AttendanceRecord.query.filter_by(user_id=current_user.id).order_by(AttendanceRecord.work_date.desc()).limit(20).all()
    return render_template("attendance.html", record=record, history=history, today=today)


@bp.get("/admin/attendance.csv")
@login_required
def attendance_export():
    denied = admin_only()
    if denied:
        return denied
    try:
        from_date = date.fromisoformat(request.args.get("from_date", "")) if request.args.get("from_date") else date.today().replace(day=1)
        to_date = date.fromisoformat(request.args.get("to_date", "")) if request.args.get("to_date") else date.today()
    except ValueError:
        return "Invalid date range", 400
    if to_date < from_date:
        return "Invalid date range", 400
    stream = StringIO(); writer = csv.writer(stream)
    writer.writerow(["Employee Code", "Employee", "Department", "Location", "Work Date", "Checked In", "Checked Out", "Hours Worked"])
    records = AttendanceRecord.query.join(User).filter(AttendanceRecord.work_date.between(from_date, to_date)).order_by(AttendanceRecord.work_date, AttendanceRecord.user_id).all()
    for item in records:
        profile = item.user.employee_profile
        hours = round((item.checked_out_at - item.checked_in_at).total_seconds() / 3600, 2) if item.checked_out_at else ""
        writer.writerow([profile.employee_code if profile else "", profile.full_name if profile else item.user.username, profile.department.name if profile and profile.department else "", profile.location.name if profile and profile.location else "", item.work_date.isoformat(), item.checked_in_at.isoformat(sep=" "), item.checked_out_at.isoformat(sep=" ") if item.checked_out_at else "", hours])
    return send_file(BytesIO(stream.getvalue().encode()), mimetype="text/csv", as_attachment=True, download_name=f"pointlabs-attendance-{from_date}-{to_date}.csv")


@bp.route("/documents", methods=["GET", "POST"])
@login_required
def documents():
    if request.method == "POST":
        owner_id = request.form.get("employee_user_id", type=int) if current_user.has_hr_access else current_user.id
        owner = db.session.get(User, owner_id) if owner_id else None
        if owner is None or (not current_user.has_hr_access and owner.id != current_user.id):
            return "Employee selection is invalid", 400
        file = request.files.get("file")
        if not file or not file.filename:
            flash("Choose a document to upload.")
            return redirect(url_for("main.documents"))
        try:
            safe, mime_type, size = store_uploaded_file(file, f"employee-{owner.id}")
        except ValueError as error:
            flash(str(error))
            return redirect(url_for("main.documents"))
        db.session.add(EmployeeDocument(
            user_id=owner.id,
            category=request.form.get("category", "Other").strip() or "Other",
            filename=file.filename,
            stored_path=safe,
            mime_type=mime_type,
            file_size=size,
            is_employee_visible=bool(request.form.get("is_employee_visible")),
            uploaded_by_id=current_user.id,
        ))
        db.session.commit()
        flash(f"Document uploaded to {display_name(owner)}’s profile.")
        return redirect(url_for("main.documents"))
    docs = EmployeeDocument.query.order_by(EmployeeDocument.uploaded_at.desc()) if current_user.has_hr_access else EmployeeDocument.query.filter_by(user_id=current_user.id, is_employee_visible=True).order_by(EmployeeDocument.uploaded_at.desc())
    return render_template("documents.html", documents=docs.all(), employees=EmployeeProfile.query.order_by(EmployeeProfile.full_name).all() if current_user.has_hr_access else [])


@bp.get("/documents/<int:document_id>/download")
@login_required
def download_document(document_id):
    document = db.get_or_404(EmployeeDocument, document_id)
    if not (current_user.has_hr_access or (document.user_id == current_user.id and document.is_employee_visible)):
        return "Forbidden", 403
    return send_from_directory(Path(current_app.instance_path) / "uploads", document.stored_path, as_attachment=True, download_name=document.filename)


@bp.route("/messages", methods=["GET", "POST"])
@login_required
def messages():
    peers = User.query.filter(User.id != current_user.id, User.is_active.is_(True)).order_by(User.username).all()
    selected_id = request.values.get("recipient_id", type=int)
    selected = db.session.get(User, selected_id) if selected_id else (peers[0] if peers else None)
    if selected and selected.id == current_user.id:
        selected = None
    if request.method == "POST":
        body = request.form.get("body", "").strip()
        if selected is None or not body:
            flash("Select a colleague and write a message.")
            return redirect(url_for("main.messages"))
        db.session.add(DirectMessage(sender_id=current_user.id, recipient_id=selected.id, body=body))
        db.session.add(Notification(user_id=selected.id, message=f"New message from {display_name(current_user)}."))
        db.session.commit()
        if selected.email:
            send_message_email(selected.email, display_name(current_user), body)
        return redirect(url_for("main.messages", recipient_id=selected.id))
    thread = []
    if selected:
        thread = DirectMessage.query.filter(or_((DirectMessage.sender_id == current_user.id) & (DirectMessage.recipient_id == selected.id), (DirectMessage.sender_id == selected.id) & (DirectMessage.recipient_id == current_user.id))).order_by(DirectMessage.created_at).all()
        for item in thread:
            if item.recipient_id == current_user.id:
                item.is_read = True
        db.session.commit()
    return render_template("messages.html", peers=peers, selected=selected, thread=thread)


@bp.get("/reports")
@login_required
def reports():
    denied = admin_only()
    if denied:
        return denied
    try:
        from_date = date.fromisoformat(request.args.get("from_date")) if request.args.get("from_date") else date.today().replace(month=1, day=1)
        to_date = date.fromisoformat(request.args.get("to_date")) if request.args.get("to_date") else date.today()
    except ValueError:
        from_date, to_date = date.today().replace(month=1, day=1), date.today()
    leaves = LeaveRequest.query.filter(LeaveRequest.start_date <= to_date, LeaveRequest.end_date >= from_date).order_by(LeaveRequest.created_at.desc()).all()
    annual_sick = LeaveBalance.query.join(LeaveType).filter(LeaveBalance.calendar_year == from_date.year, LeaveType.code.in_(["ANNUAL", "SICK"])).all()
    return render_template("reports.html", employees=EmployeeProfile.query.filter(EmployeeProfile.employment_status == "active").count(), pending=LeaveRequest.query.filter(LeaveRequest.status.in_(["submitted", "cancellation_requested"])).count(), approved=LeaveRequest.query.filter_by(status="approved").count(), leaves=leaves[:8], balances=annual_sick, from_date=from_date, to_date=to_date)


@bp.get("/reports/leave.csv")
@login_required
def leave_report():
    if not (current_user.is_administrator or current_user.employee_profile):
        return "Forbidden", 403
    stream = StringIO(); writer = csv.writer(stream); writer.writerow(["Employee", "Leave type", "Start", "End", "Days", "Status"])
    for item in LeaveRequest.query.order_by(LeaveRequest.created_at.desc()).all():
        writer.writerow([display_name(item.user), item.leave_type.name, item.start_date, item.end_date, item.days, item.status])
    return send_file(BytesIO(stream.getvalue().encode()), mimetype="text/csv", as_attachment=True, download_name="pointlabs-leave-report.csv")


@bp.get("/reports/leave-summary.csv")
@login_required
def leave_summary_report():
    denied = admin_only()
    if denied:
        return denied
    year = request.args.get("year", date.today().year, type=int)
    stream = StringIO(); writer = csv.writer(stream)
    writer.writerow(["Employee", "Employee Code", "Department", "Location", "Leave Type", "Entitled", "Accrued", "Utilized", "Balance"])
    for balance in LeaveBalance.query.join(LeaveType).filter(LeaveBalance.calendar_year == year, LeaveType.code.in_(["ANNUAL", "SICK"])).order_by(LeaveBalance.user_id).all():
        profile = ensure_profile(balance.user)
        writer.writerow([profile.full_name, profile.employee_code or "", profile.department.name if profile.department else "", profile.location.name if profile.location else "", balance.leave_type.name, balance.entitled_days, balance.accrued_days, balance.utilized_days, balance.available_days])
    return send_file(BytesIO(stream.getvalue().encode()), mimetype="text/csv", as_attachment=True, download_name=f"pointlabs-leave-summary-{year}.csv")


@bp.get("/reports/employees.csv")
@login_required
def full_employee_report():
    denied = admin_only()
    if denied:
        return denied
    stream = StringIO(); writer = csv.writer(stream)
    writer.writerow(["Employee Code", "Full Name", "Preferred Name", "Work Email", "Entity", "Location", "Department", "Designation", "Manager", "Date Joined", "Status"])
    for profile in EmployeeProfile.query.order_by(EmployeeProfile.full_name).all():
        writer.writerow([profile.employee_code or "", profile.full_name, profile.preferred_name or "", profile.user.email or "", profile.entity.name if profile.entity else "", profile.location.name if profile.location else "", profile.department.name if profile.department else "", profile.designation.name if profile.designation else "", profile.reporting_officer.employee_profile.full_name if profile.reporting_officer and profile.reporting_officer.employee_profile else "", profile.date_of_joining or "", profile.employment_status])
    return send_file(BytesIO(stream.getvalue().encode()), mimetype="text/csv", as_attachment=True, download_name="pointlabs-full-employee-detail.csv")


@bp.get("/admin")
@login_required
def admin_panel():
    denied = admin_only()
    if denied:
        return denied
    return render_template(
        "admin_panel.html", people_count=EmployeeProfile.query.count(),
        documents_count=EmployeeDocument.query.count(),
        pending_count=LeaveRequest.query.filter(LeaveRequest.status.in_(("submitted", "returned", "cancellation_requested"))).count(),
        pending_request_count=OtherRequest.query.filter(OtherRequest.status.in_(("submitted", "resubmitted", "more_information_required", "in_review", "in_progress"))).count(),
    )


@bp.get("/admin/audit")
@login_required
def audit_log():
    denied = admin_only()
    if denied:
        return denied
    entity_type = request.args.get("entity_type", "").strip()
    actor_id = request.args.get("actor_id", type=int)
    query = AuditEvent.query.order_by(AuditEvent.created_at.desc())
    if entity_type:
        query = query.filter_by(entity_type=entity_type)
    if actor_id:
        query = query.filter_by(actor_id=actor_id)
    page = query.paginate(page=max(1, request.args.get("page", 1, type=int)), per_page=25, error_out=False)
    types = [item[0] for item in db.session.query(AuditEvent.entity_type).distinct().order_by(AuditEvent.entity_type).all()]
    return render_template("audit_log.html", events=page, entity_type=entity_type, actor_id=actor_id, entity_types=types, actors=User.query.filter_by(is_active=True).order_by(User.username).all())


@bp.route("/admin/designations", methods=["GET", "POST"])
@login_required
def designations():
    denied = configuration_only()
    if denied:
        return denied
    if request.method == "POST":
        name = request.form["name"].strip()
        if name and not Designation.query.filter_by(name=name).first():
            db.session.add(Designation(name=name, is_reporting_officer_designation=bool(request.form.get("reporting")))); db.session.commit()
        return redirect(url_for("main.designations"))
    return render_template("designations.html", designations=Designation.query.order_by(Designation.name).all())


@bp.post("/admin/designations/<int:designation_id>/toggle")
@login_required
def toggle_designation(designation_id):
    denied = configuration_only()
    if denied:
        return denied
    item = db.get_or_404(Designation, designation_id); item.is_reporting_officer_designation = not item.is_reporting_officer_designation; db.session.commit()
    return redirect(url_for("main.designations"))


@bp.route("/admin/access-roles", methods=["GET", "POST"])
@login_required
def access_roles():
    denied = configuration_only()
    if denied:
        return denied
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name or AccessRole.query.filter_by(name=name).first():
            flash("Enter a unique access role name.")
        else:
            db.session.add(AccessRole(name=name, description=request.form.get("description", "").strip() or None, grants_hr_access=bool(request.form.get("grants_hr_access")), can_manage_configuration=bool(request.form.get("can_manage_configuration"))))
            db.session.commit(); flash("Access role created.")
        return redirect(url_for("main.access_roles"))
    return render_template("access_roles.html", roles=AccessRole.query.order_by(AccessRole.name).all())


@bp.post("/admin/access-roles/<int:role_id>/toggle")
@login_required
def toggle_access_role(role_id):
    denied = configuration_only()
    if denied:
        return denied
    role = db.get_or_404(AccessRole, role_id)
    # Archive rather than delete: role assignment and historic workflow decisions stay valid.
    role.is_active = not role.is_active
    db.session.add(AuditEvent(actor_id=current_user.id, entity_type="access_role", entity_id=role.id, action="activated" if role.is_active else "archived", summary=f"Access role {role.name} was {'activated' if role.is_active else 'archived'}."))
    db.session.commit()
    flash("Access role status updated. Existing assignments and historical decisions were retained.")
    return redirect(url_for("main.access_roles"))


@bp.route("/admin/workflows", methods=["GET", "POST"])
@login_required
def workflows():
    denied = configuration_only()
    if denied:
        return denied
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        applies_to = request.form.get("applies_to")
        if not name or applies_to not in {"leave", "other_request"} or ApprovalWorkflow.query.filter_by(name=name).first():
            flash("Enter a unique workflow name and valid request area.")
        else:
            db.session.add(ApprovalWorkflow(name=name, applies_to=applies_to, description=request.form.get("description", "").strip() or None, created_by_id=current_user.id))
            db.session.commit(); flash("Approval workflow created. Add at least one approval step before activating it.")
        return redirect(url_for("main.workflows"))
    return render_template("workflows.html", workflows=ApprovalWorkflow.query.order_by(ApprovalWorkflow.applies_to, ApprovalWorkflow.name).all(), designations=Designation.query.filter_by(is_active=True).order_by(Designation.name).all(), users=User.query.filter_by(is_active=True).order_by(User.username).all(), access_roles=AccessRole.query.filter_by(is_active=True).order_by(AccessRole.name).all(), request_types=_request_types())


@bp.post("/admin/workflows/<int:workflow_id>/steps")
@login_required
def add_workflow_step(workflow_id):
    denied = configuration_only()
    if denied:
        return denied
    workflow = db.get_or_404(ApprovalWorkflow, workflow_id)
    kind = request.form.get("approver_kind")
    designation_id = request.form.get("designation_id", type=int)
    user_id = request.form.get("approver_user_id", type=int)
    role_id = request.form.get("access_role_id", type=int)
    if kind not in {"designation", "direct_manager", "named_user", "hr_access", "access_role"}:
        flash("Choose a valid approver type.")
    elif kind == "designation" and not db.session.get(Designation, designation_id):
        flash("Choose an active designation for this approval step.")
    elif kind == "named_user" and not db.session.get(User, user_id):
        flash("Choose an active named approver.")
    elif kind == "access_role" and not db.session.get(AccessRole, role_id):
        flash("Choose an active access role for this approval step.")
    else:
        next_order = max((step.step_order for step in workflow.steps), default=0) + 1
        db.session.add(ApprovalWorkflowStep(workflow_id=workflow.id, step_order=next_order, approval_mode=request.form.get("approval_mode") if request.form.get("approval_mode") in {"any", "all"} else "any", approver_kind=kind, designation_id=designation_id if kind == "designation" else None, approver_user_id=user_id if kind == "named_user" else None, access_role_id=role_id if kind == "access_role" else None))
        db.session.commit(); flash("Approval step added.")
    return redirect(url_for("main.workflows"))


@bp.post("/admin/workflows/<int:workflow_id>/toggle")
@login_required
def toggle_workflow(workflow_id):
    denied = configuration_only()
    if denied:
        return denied
    workflow = db.get_or_404(ApprovalWorkflow, workflow_id)
    if not workflow.is_active and not workflow.steps:
        flash("Add an approval step before activating a workflow.")
    else:
        workflow.is_active = not workflow.is_active
        db.session.commit(); flash("Workflow status updated.")
    return redirect(url_for("main.workflows"))


@bp.post("/admin/request-types")
@login_required
def request_types():
    denied = configuration_only()
    if denied:
        return denied
    name = request.form.get("name", "").strip()
    if not name or RequestType.query.filter_by(name=name).first():
        flash("Enter a unique service request name.")
    else:
        db.session.add(RequestType(name=name, description=request.form.get("description", "").strip() or None, workflow_id=request.form.get("workflow_id", type=int)))
        db.session.commit(); flash("Service request type added.")
    return redirect(url_for("main.workflows"))


@bp.get("/birthdays")
@login_required
def birthdays():
    denied = admin_only()
    if denied:
        return denied
    until = date.today() + timedelta(days=3)
    people = [profile for profile in EmployeeProfile.query.all() if profile.date_of_birth and date.today() <= profile.date_of_birth.replace(year=date.today().year) <= until]
    return render_template("birthdays.html", people=people)


DEFAULT_REQUEST_CATEGORIES = (
    "Salary Certificate", "Employment / Experience Certificate", "Employment Verification Letter",
    "NOC Request", "Salary Transfer Letter", "Personal Information Update",
    "Employee Document Copy Request", "Visa Application Support Letter", "Other HR Request",
)


def _request_types():
    """The historic catalogue remains readable; new choices are HR-managed records."""
    return RequestType.query.filter_by(is_active=True).order_by(RequestType.name).all()


def _request_access(item):
    return current_user.has_hr_access or item.user_id == current_user.id


@bp.route("/requests", methods=["GET", "POST"])
@login_required
def other_requests():
    if request.method == "POST":
        request_type_id = request.form.get("request_type_id", type=int)
        request_type = db.session.get(RequestType, request_type_id) if request_type_id else None
        # Compatibility for existing bookmarked forms and historic integrations. The
        # generated catalogue remains admin-manageable after this one-time mapping.
        legacy_category = request.form.get("category", "").strip()
        if request_type is None and legacy_category in DEFAULT_REQUEST_CATEGORIES:
            request_type = RequestType.query.filter_by(name=legacy_category).first()
            if request_type is None:
                request_type = RequestType(name=legacy_category, description="Initial Pointlabs HR service catalogue item.")
                db.session.add(request_type)
                db.session.flush()
        details = request.form.get("details", "").strip()
        if request_type is None or not request_type.is_active or not details:
            flash("Choose a request category and describe what you need.")
            return redirect(url_for("main.other_requests"))
        category = request_type.name
        item = OtherRequest(user_id=current_user.id, request_type_id=request_type.id, category=category, subject=request.form.get("subject", "").strip() or None, details=details)
        db.session.add(item)
        db.session.flush()
        db.session.add(OtherRequestActivity(other_request_id=item.id, actor_id=current_user.id, activity_type="submitted", message="Request submitted."))
        workflow = active_workflow("other_request", request_type)
        try:
            instance = start_workflow(workflow, "other_request", item.id, current_user)
        except ValueError as error:
            db.session.rollback()
            flash(str(error))
            return redirect(url_for("main.other_requests"))
        if instance:
            for decision in instance.decisions:
                db.session.add(Notification(user_id=decision.approver_id, message=f"New {category} request from {display_name(current_user)} needs your approval."))
        else:
            for administrator in _hr_users():
                db.session.add(Notification(user_id=administrator.id, message=f"New {category} request from {display_name(current_user)}."))
        db.session.commit()
        flash("Your request has been submitted to HR.")
        return redirect(url_for("main.other_request_detail", request_id=item.id))
    query = OtherRequest.query.order_by(OtherRequest.updated_at.desc())
    if not current_user.has_hr_access:
        query = query.filter_by(user_id=current_user.id)
    status = request.args.get("status", "").strip()
    if status:
        query = query.filter_by(status=status)
    return render_template("other_requests.html", requests=query.paginate(page=max(1, request.args.get("page", 1, type=int)), per_page=10, error_out=False), categories=_request_types(), selected_status=status)


@bp.route("/requests/<int:request_id>", methods=["GET", "POST"])
@login_required
def other_request_detail(request_id):
    item = db.get_or_404(OtherRequest, request_id)
    if not _request_access(item):
        return "Forbidden", 403
    if request.method == "POST":
        action = request.form.get("action")
        message = request.form.get("message", "").strip()
        employee_editable = item.status in {"draft", "submitted", "more_information_required", "resubmitted"}
        if action == "edit" and item.user_id == current_user.id and employee_editable:
            details = request.form.get("details", "").strip()
            if details:
                item.subject, item.details, item.status = request.form.get("subject", "").strip() or None, details, "resubmitted" if item.status == "more_information_required" else item.status
                db.session.add(OtherRequestActivity(other_request_id=item.id, actor_id=current_user.id, activity_type="employee_updated", message="Employee updated request details."))
                instance = ApprovalInstance.query.filter_by(subject_type="other_request", subject_id=item.id).first()
                if instance and resubmit_after_more_information(instance):
                    item.status = "submitted"
                    for decision in instance.decisions:
                        if decision.status == "pending":
                            db.session.add(Notification(user_id=decision.approver_id, message=f"{display_name(current_user)} supplied the requested information for {item.category}."))
        elif action == "cancel" and item.user_id == current_user.id and item.status not in {"completed", "cancelled", "rejected"}:
            item.status, item.cancelled_at = "cancelled", datetime.utcnow()
            db.session.add(OtherRequestActivity(other_request_id=item.id, actor_id=current_user.id, activity_type="cancelled", message="Employee cancelled this request."))
        elif current_user.has_hr_access and action in {"in_review", "more_information_required", "in_progress", "completed", "rejected"}:
            if ApprovalInstance.query.filter_by(subject_type="other_request", subject_id=item.id, status="pending").first():
                return "This request must be decided through its configured approval workflow", 409
            item.status = action
            db.session.add(OtherRequestActivity(other_request_id=item.id, actor_id=current_user.id, activity_type=action, message=message or action.replace("_", " ").title()))
            db.session.add(Notification(user_id=item.user_id, message="Your request has been updated." if action != "completed" else "Your HR request has been completed."))
            if item.user.email:
                send_notice_email(item.user.email, "Pointlabs One · Request update", "Your request has been updated." if action != "completed" else "Your HR request has been completed. Visit Pointlabs One to view the details.")
        elif action == "comment" and message:
            internal = bool(request.form.get("internal")) and current_user.has_hr_access
            db.session.add(OtherRequestActivity(other_request_id=item.id, actor_id=current_user.id, activity_type="comment", message=message, is_internal=internal))
            if current_user.has_hr_access and not internal:
                db.session.add(Notification(user_id=item.user_id, message="HR added an update to your request."))
        else:
            return "Invalid request action", 409
        db.session.commit()
        flash("Request updated.")
        return redirect(url_for("main.other_request_detail", request_id=item.id))
    activities = [activity for activity in item.activities if current_user.has_hr_access or not activity.is_internal]
    return render_template("other_request_detail.html", item=item, activities=activities)


@bp.route("/admin/master-data/<string:kind>", methods=["GET", "POST"])
@login_required
def master_data(kind):
    denied = configuration_only()
    if denied:
        return denied
    models = {"departments": Department, "locations": Location, "entities": Entity}
    model = models.get(kind)
    if model is None:
        abort(404)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name or model.query.filter_by(name=name).first():
            flash("Enter a unique name.")
        else:
            item = model(name=name)
            if model is Location:
                item.entity_id = request.form.get("entity_id", type=int)
                item.country_code = request.form.get("country_code", "").strip().upper() or None
            if model is Entity:
                item.legal_name = request.form.get("legal_name", "").strip() or None
                item.country_code = request.form.get("country_code", "").strip().upper() or None
                item.currency = request.form.get("currency", "").strip().upper() or None
            db.session.add(item); db.session.commit(); flash("Master record added.")
        return redirect(url_for("main.master_data", kind=kind))
    return render_template("master_data.html", kind=kind, records=model.query.order_by(model.name).all(), entities=Entity.query.filter_by(is_active=True).order_by(Entity.name).all())


@bp.route("/admin/public-holidays", methods=["GET", "POST"])
@login_required
def public_holidays():
    denied = configuration_only()
    if denied:
        return denied
    if request.method == "POST":
        try:
            holiday_date = date.fromisoformat(request.form["holiday_date"])
        except (KeyError, ValueError):
            flash("Choose a valid public holiday date.")
            return redirect(url_for("main.public_holidays"))
        name = request.form.get("name", "").strip()
        if not name:
            flash("Enter a public holiday name.")
            return redirect(url_for("main.public_holidays"))
        existing = PublicHoliday.query.filter_by(
            name=name, holiday_date=holiday_date,
            location_id=request.form.get("location_id", type=int), entity_id=request.form.get("entity_id", type=int),
        ).first()
        if existing:
            flash("That holiday already exists for this entity/location scope.")
            return redirect(url_for("main.public_holidays"))
        db.session.add(PublicHoliday(name=name, holiday_date=holiday_date, location_id=request.form.get("location_id", type=int), entity_id=request.form.get("entity_id", type=int)))
        db.session.commit(); flash("Public holiday added.")
        return redirect(url_for("main.public_holidays"))
    return render_template("public_holidays.html", holidays=PublicHoliday.query.order_by(PublicHoliday.holiday_date).all(), locations=Location.query.filter_by(is_active=True).all(), entities=Entity.query.filter_by(is_active=True).all())


@bp.post("/admin/public-holidays/<int:holiday_id>/edit")
@login_required
def edit_public_holiday(holiday_id):
    denied = configuration_only()
    if denied:
        return denied
    item = db.get_or_404(PublicHoliday, holiday_id)
    try:
        holiday_date = date.fromisoformat(request.form.get("holiday_date", ""))
    except ValueError:
        flash("Choose a valid public holiday date.")
        return redirect(url_for("main.public_holidays"))
    name = request.form.get("name", "").strip()
    if not name:
        flash("Enter a public holiday name.")
        return redirect(url_for("main.public_holidays"))
    duplicate = PublicHoliday.query.filter(
        PublicHoliday.id != item.id,
        PublicHoliday.name == name,
        PublicHoliday.holiday_date == holiday_date,
        PublicHoliday.entity_id == request.form.get("entity_id", type=int),
        PublicHoliday.location_id == request.form.get("location_id", type=int),
    ).first()
    if duplicate:
        flash("That holiday already exists for this entity/location scope.")
        return redirect(url_for("main.public_holidays"))
    item.name, item.holiday_date = name, holiday_date
    item.entity_id = request.form.get("entity_id", type=int)
    item.location_id = request.form.get("location_id", type=int)
    item.is_active = bool(request.form.get("is_active"))
    db.session.commit()
    flash("Public holiday updated. Leave calculations will use the new scoped calendar.")
    return redirect(url_for("main.public_holidays"))


def _money(value):
    try:
        amount = Decimal(request.form.get(value, "0") or "0")
    except InvalidOperation:
        raise ValueError(f"{value.replace('_', ' ').title()} must be a valid amount.")
    if amount < 0:
        raise ValueError("Salary values cannot be negative.")
    return amount.quantize(Decimal("0.01"))


def _current_compensation(user, effective_date=None):
    query = CompensationRecord.query.filter_by(user_id=user.id)
    if effective_date:
        query = query.filter(CompensationRecord.effective_date <= effective_date)
    return query.order_by(CompensationRecord.effective_date.desc(), CompensationRecord.id.desc()).first()


@bp.get("/admin/payroll")
@login_required
def payroll():
    denied = admin_only()
    if denied:
        return denied
    year = request.args.get("year", date.today().year, type=int)
    month = request.args.get("month", date.today().month, type=int)
    if month not in range(1, 13):
        month = date.today().month
    selected_user_id = request.args.get("user_id", type=int)
    profile_query = EmployeeProfile.query.join(User, EmployeeProfile.user_id == User.id).filter(User.is_active.is_(True))
    if selected_user_id:
        profile_query = profile_query.filter(EmployeeProfile.user_id == selected_user_id)
    profiles = profile_query.order_by(EmployeeProfile.full_name).all()
    period_start = date(year, month, 1)
    compensation_by_user = {
        profile.user_id: _current_compensation(profile.user, period_start)
        for profile in profiles
    }
    payslips = Payslip.query.filter_by(payroll_year=year, payroll_month=month).order_by(Payslip.generated_at.desc()).all()
    return render_template("payroll.html", profiles=profiles, payslips=payslips, compensation_by_user=compensation_by_user, year=year, month=month, month_name=period_start.strftime("%B"), date=date, selected_user_id=selected_user_id)


@bp.post("/admin/payroll/compensation/<int:user_id>")
@login_required
def save_compensation(user_id):
    denied = admin_only()
    if denied:
        return denied
    user = db.get_or_404(User, user_id)
    try:
        effective_date = date.fromisoformat(request.form.get("effective_date") or date.today().isoformat())
        record = CompensationRecord(
            user_id=user.id,
            effective_date=effective_date,
            currency=request.form.get("currency", "LKR").upper(),
            basic_salary=_money("basic_salary"), allowances=_money("allowances"), other_earnings=_money("other_earnings"),
            wht=_money("wht"), epf=_money("epf"), etf=_money("etf"), paye=_money("paye"), other_deductions=_money("other_deductions"),
            created_by_id=current_user.id,
        )
    except ValueError as error:
        flash(str(error)); return redirect(url_for("main.payroll"))
    db.session.add(record); db.session.commit()
    flash("Compensation revision saved with an effective date.")
    return redirect(url_for("main.payroll"))


@bp.post("/admin/payroll/generate/<int:user_id>")
@login_required
def generate_payslip(user_id):
    denied = admin_only()
    if denied:
        return denied
    user = db.get_or_404(User, user_id)
    year, month = request.form.get("year", type=int), request.form.get("month", type=int)
    if not year or month not in range(1, 13):
        return "Invalid payroll period", 400
    record = _current_compensation(user, date(year, month, 1))
    if record is None:
        flash("Add a compensation revision before generating a payslip.")
        return redirect(url_for("main.payroll", year=year, month=month))
    existing = Payslip.query.filter_by(user_id=user.id, payroll_year=year, payroll_month=month).order_by(Payslip.version.desc()).first()
    version = existing.version + 1 if existing else 1
    profile = ensure_profile(user)
    country = "AE" if (profile.location and profile.location.country_code == "AE") or (profile.entity and profile.entity.country_code == "AE") else "LK"
    payslip = Payslip(
        user_id=user.id, compensation_record_id=record.id, payroll_year=year, payroll_month=month, version=version,
        template_country=country, currency=record.currency, basic_salary=record.basic_salary, allowances=record.allowances,
        other_earnings=record.other_earnings, wht=record.wht, epf=record.epf, etf=record.etf, paye=record.paye,
        other_deductions=record.other_deductions, gross_salary=record.gross_salary, total_deductions=record.total_deductions,
        net_salary=record.net_salary, status="generating", generated_by_id=current_user.id,
    )
    db.session.add(payslip)
    db.session.flush()
    try:
        stored_path, filename = generate_payslip_pdf(payslip)
    except Exception:
        current_app.logger.exception("Payslip PDF generation failed for payslip %s", payslip.id)
        payslip.status = "generation_failed"
        payslip.pdf_generation_error = "The payslip PDF could not be generated."
        db.session.add(AuditEvent(actor_id=current_user.id, entity_type="payslip", entity_id=payslip.id, action="pdf_generation_failed", summary="Server-side payslip PDF generation failed."))
        db.session.commit()
        flash("Payslip record created, but the PDF could not be generated. No email was sent.")
        return redirect(url_for("main.payslip_detail", payslip_id=payslip.id))
    payslip.pdf_stored_path = stored_path
    payslip.pdf_filename = filename
    payslip.pdf_generated_at = datetime.utcnow()
    payslip.pdf_generation_error = None
    payslip.status = "generated"
    period = date(year, month, 1).strftime("%B %Y")
    db.session.add(Notification(user_id=user.id, message=f"Your {period} payslip is available."))
    db.session.add(AuditEvent(actor_id=current_user.id, entity_type="payslip", entity_id=payslip.id, action="pdf_generated", summary=f"Generated payslip PDF version {version} for {period}."))
    db.session.commit()
    if user.email and send_payslip_email(user.email, display_name(user), period, payslip_pdf_path(stored_path), filename):
        payslip.emailed_at = datetime.utcnow()
        db.session.commit()
    flash("Payslip PDF generated. A new version preserves prior payroll history.")
    return redirect(url_for("main.payslip_detail", payslip_id=payslip.id))


@bp.get("/payslips")
@login_required
def payslips():
    query = Payslip.query.order_by(Payslip.payroll_year.desc(), Payslip.payroll_month.desc(), Payslip.version.desc())
    if not current_user.has_hr_access:
        query = query.filter_by(user_id=current_user.id)
    return render_template("payslips.html", payslips=query.all())


@bp.get("/payslips/<int:payslip_id>")
@login_required
def payslip_detail(payslip_id):
    payslip = db.get_or_404(Payslip, payslip_id)
    if not (current_user.has_hr_access or payslip.user_id == current_user.id):
        return "Forbidden", 403
    return render_template("payslip.html", payslip=payslip, profile=ensure_profile(payslip.user), period=date(payslip.payroll_year, payslip.payroll_month, 1))


@bp.get("/payslips/<int:payslip_id>/download")
@login_required
def download_payslip(payslip_id):
    payslip = db.get_or_404(Payslip, payslip_id)
    if not (current_user.has_hr_access or payslip.user_id == current_user.id):
        return "Forbidden", 403
    if not payslip.pdf_stored_path:
        abort(404)
    path = payslip_pdf_path(payslip.pdf_stored_path)
    if not path.is_file():
        current_app.logger.error("Payslip PDF is missing for payslip %s", payslip.id)
        abort(404)
    return send_from_directory(path.parent, path.name, as_attachment=True, download_name=payslip.pdf_filename)


@bp.post("/admin/payslips/<int:payslip_id>/email")
@login_required
def email_payslip(payslip_id):
    denied = admin_only()
    if denied:
        return denied
    payslip = db.get_or_404(Payslip, payslip_id)
    path = payslip_pdf_path(payslip.pdf_stored_path) if payslip.pdf_stored_path else None
    if not path or not path.is_file():
        flash("No generated PDF is available to send for this payslip.")
    elif payslip.user.email:
        period = date(payslip.payroll_year, payslip.payroll_month, 1).strftime("%B %Y")
        if send_payslip_email(payslip.user.email, display_name(payslip.user), period, path, payslip.pdf_filename):
            payslip.emailed_at = datetime.utcnow()
            db.session.commit()
            flash("Confidential payslip PDF email sent.")
        else:
            flash("Payslip email could not be sent. The PDF remains available securely in the portal.")
    else:
        flash("This employee has no work email address.")
    return redirect(url_for("main.payslip_detail", payslip_id=payslip.id))
