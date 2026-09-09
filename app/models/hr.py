from datetime import datetime
from app.extensions import db


class LeaveType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    default_days = db.Column(db.Float, nullable=False, default=0)
    code = db.Column(db.String(30), nullable=True, unique=True)
    accrual_method = db.Column(db.String(30), nullable=False, default="annual")
    requires_manager_approval = db.Column(db.Boolean, nullable=False, default=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)


class LeaveBalance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    leave_type_id = db.Column(db.Integer, db.ForeignKey("leave_type.id"), nullable=False)
    available_days = db.Column(db.Float, nullable=False, default=0)
    calendar_year = db.Column(db.Integer, nullable=False, default=lambda: datetime.utcnow().year)
    entitled_days = db.Column(db.Float, nullable=False, default=0)
    accrued_days = db.Column(db.Float, nullable=False, default=0)
    utilized_days = db.Column(db.Float, nullable=False, default=0)
    carry_forward_days = db.Column(db.Float, nullable=False, default=0)
    adjustment_days = db.Column(db.Float, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    user = db.relationship("User")
    leave_type = db.relationship("LeaveType")

    __table_args__ = (db.UniqueConstraint("user_id", "leave_type_id", "calendar_year", name="uq_leave_balance_user_type_year"),)


class LeaveRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    leave_type_id = db.Column(db.Integer, db.ForeignKey("leave_type.id"), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    days = db.Column(db.Float, nullable=False)
    reason = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(30), nullable=False, default="submitted")
    reviewer_comment = db.Column(db.Text, nullable=True)
    approver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    balance_applied = db.Column(db.Boolean, nullable=False, default=False)
    cancellation_requested_at = db.Column(db.DateTime, nullable=True)
    cancellation_reason = db.Column(db.Text, nullable=True)
    cancellation_reviewer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    confirmation_reference = db.Column(db.String(80), nullable=True, unique=True, index=True)
    confirmation_stored_path = db.Column(db.String(255), nullable=True)
    confirmation_filename = db.Column(db.String(255), nullable=True)
    confirmation_generated_at = db.Column(db.DateTime, nullable=True)
    confirmation_emailed_at = db.Column(db.DateTime, nullable=True)
    confirmation_generation_error = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    user = db.relationship("User", foreign_keys=[user_id])
    leave_type = db.relationship("LeaveType")
    approver = db.relationship("User", foreign_keys=[approver_id])
    cancellation_reviewer = db.relationship("User", foreign_keys=[cancellation_reviewer_id])


class EmployeeDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(120), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)
    is_employee_visible = db.Column(db.Boolean, nullable=False, default=True)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user = db.relationship("User", foreign_keys=[user_id])


class PublicHoliday(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    holiday_date = db.Column(db.Date, nullable=False, index=True)
    location_id = db.Column(db.Integer, db.ForeignKey("location.id"), nullable=True, index=True)
    entity_id = db.Column(db.Integer, db.ForeignKey("entity.id"), nullable=True, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    location = db.relationship("Location")
    entity = db.relationship("Entity")

    __table_args__ = (db.UniqueConstraint("holiday_date", "location_id", "entity_id", "name", name="uq_public_holiday_scope"),)


class LeaveBalanceAdjustment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    leave_balance_id = db.Column(db.Integer, db.ForeignKey("leave_balance.id"), nullable=False, index=True)
    changed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    days = db.Column(db.Float, nullable=False)
    reason = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    balance = db.relationship("LeaveBalance", backref="adjustments")
    changed_by = db.relationship("User", foreign_keys=[changed_by_id])


class CompensationRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    effective_date = db.Column(db.Date, nullable=False, index=True)
    currency = db.Column(db.String(3), nullable=False, default="LKR")
    basic_salary = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    allowances = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    other_earnings = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    wht = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    epf = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    etf = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    paye = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    other_deductions = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user = db.relationship("User", foreign_keys=[user_id], backref="compensation_records")
    created_by = db.relationship("User", foreign_keys=[created_by_id])

    @property
    def gross_salary(self):
        return self.basic_salary + self.allowances + self.other_earnings

    @property
    def total_deductions(self):
        return self.wht + self.epf + self.etf + self.paye + self.other_deductions

    @property
    def net_salary(self):
        return self.gross_salary - self.total_deductions


class Payslip(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    compensation_record_id = db.Column(db.Integer, db.ForeignKey("compensation_record.id"), nullable=True)
    payroll_year = db.Column(db.Integer, nullable=False, index=True)
    payroll_month = db.Column(db.Integer, nullable=False, index=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    template_country = db.Column(db.String(2), nullable=False, default="LK")
    currency = db.Column(db.String(3), nullable=False)
    basic_salary = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    allowances = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    other_earnings = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    wht = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    epf = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    etf = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    paye = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    other_deductions = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    gross_salary = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    total_deductions = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    net_salary = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    status = db.Column(db.String(30), nullable=False, default="draft")
    generated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    generated_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    emailed_at = db.Column(db.DateTime, nullable=True)
    pdf_stored_path = db.Column(db.String(255), nullable=True)
    pdf_filename = db.Column(db.String(255), nullable=True)
    pdf_generated_at = db.Column(db.DateTime, nullable=True)
    pdf_generation_error = db.Column(db.String(500), nullable=True)
    user = db.relationship("User", foreign_keys=[user_id], backref="payslips")
    compensation_record = db.relationship("CompensationRecord")
    generated_by = db.relationship("User", foreign_keys=[generated_by_id])

    __table_args__ = (db.UniqueConstraint("user_id", "payroll_year", "payroll_month", "version", name="uq_payslip_user_period_version"),)


class OtherRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    category = db.Column(db.String(80), nullable=False, index=True)
    request_type_id = db.Column(db.Integer, db.ForeignKey("request_type.id"), nullable=True, index=True)
    subject = db.Column(db.String(180), nullable=True)
    details = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(40), nullable=False, default="submitted", index=True)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    completed_document_id = db.Column(db.Integer, db.ForeignKey("employee_document.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    user = db.relationship("User", foreign_keys=[user_id], backref="other_requests")
    assigned_to = db.relationship("User", foreign_keys=[assigned_to_id])
    completed_document = db.relationship("EmployeeDocument", foreign_keys=[completed_document_id])
    request_type = db.relationship("RequestType")


class RequestType(db.Model):
    """HR service catalogue owned by HR, never by a hard-coded form list."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    description = db.Column(db.String(500), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    workflow_id = db.Column(db.Integer, db.ForeignKey("approval_workflow.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class ApprovalWorkflow(db.Model):
    """A reusable, administrator-configured approval route for HR business events."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False, unique=True)
    applies_to = db.Column(db.String(40), nullable=False, index=True)  # leave or other_request
    description = db.Column(db.String(500), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    steps = db.relationship("ApprovalWorkflowStep", backref="workflow", order_by="ApprovalWorkflowStep.step_order", cascade="all, delete-orphan")


class ApprovalWorkflowStep(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workflow_id = db.Column(db.Integer, db.ForeignKey("approval_workflow.id"), nullable=False, index=True)
    step_order = db.Column(db.Integer, nullable=False)
    # any = any one eligible approver can progress; all = every eligible approver must decide.
    approval_mode = db.Column(db.String(12), nullable=False, default="any")
    approver_kind = db.Column(db.String(24), nullable=False, default="designation")
    designation_id = db.Column(db.Integer, db.ForeignKey("designation.id"), nullable=True)
    approver_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    access_role_id = db.Column(db.Integer, db.ForeignKey("access_role.id"), nullable=True)
    designation = db.relationship("Designation")
    approver_user = db.relationship("User", foreign_keys=[approver_user_id])
    access_role = db.relationship("AccessRole")
    __table_args__ = (db.UniqueConstraint("workflow_id", "step_order", name="uq_approval_workflow_step_order"),)


class ApprovalInstance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workflow_id = db.Column(db.Integer, db.ForeignKey("approval_workflow.id"), nullable=False, index=True)
    subject_type = db.Column(db.String(40), nullable=False, index=True)
    subject_id = db.Column(db.Integer, nullable=False, index=True)
    requester_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="pending", index=True)
    current_step_order = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    workflow = db.relationship("ApprovalWorkflow")
    requester = db.relationship("User", foreign_keys=[requester_id])
    decisions = db.relationship("ApprovalDecision", backref="instance", cascade="all, delete-orphan")
    __table_args__ = (db.UniqueConstraint("subject_type", "subject_id", name="uq_approval_subject"),)


class ApprovalDecision(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    approval_instance_id = db.Column(db.Integer, db.ForeignKey("approval_instance.id"), nullable=False, index=True)
    workflow_step_id = db.Column(db.Integer, db.ForeignKey("approval_workflow_step.id"), nullable=False)
    approver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    status = db.Column(db.String(32), nullable=False, default="pending", index=True)
    comment = db.Column(db.Text, nullable=True)
    acted_at = db.Column(db.DateTime, nullable=True)
    step = db.relationship("ApprovalWorkflowStep")
    approver = db.relationship("User", foreign_keys=[approver_id])
    __table_args__ = (db.UniqueConstraint("approval_instance_id", "workflow_step_id", "approver_id", name="uq_approval_decision"),)


class OtherRequestActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    other_request_id = db.Column(db.Integer, db.ForeignKey("other_request.id"), nullable=False, index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    activity_type = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text, nullable=True)
    is_internal = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    request = db.relationship("OtherRequest", backref="activities")
    actor = db.relationship("User")


class OtherRequestAttachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    other_request_id = db.Column(db.Integer, db.ForeignKey("other_request.id"), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(120), nullable=True)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    request = db.relationship("OtherRequest", backref="attachments")
    uploaded_by = db.relationship("User")


class AuditEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    entity_type = db.Column(db.String(80), nullable=False, index=True)
    entity_id = db.Column(db.Integer, nullable=False, index=True)
    action = db.Column(db.String(80), nullable=False)
    summary = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    actor = db.relationship("User")


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class WorkspaceTask(db.Model):
    """A private, lightweight work item owned by one authenticated user."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(240), nullable=False)
    due_at = db.Column(db.DateTime, nullable=True, index=True)
    completed_at = db.Column(db.DateTime, nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user = db.relationship("User", foreign_keys=[user_id], backref="workspace_tasks")


class WorkspaceNote(db.Model):
    """A note can be personal or deliberately published by HR to every workspace."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    body = db.Column(db.String(600), nullable=False)
    color = db.Column(db.String(24), nullable=False, default="gold")
    is_global = db.Column(db.Boolean, nullable=False, default=False, index=True)
    show_everywhere = db.Column(db.Boolean, nullable=False, default=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user = db.relationship("User", foreign_keys=[user_id], backref="workspace_notes")


class DirectMessage(db.Model):
    """A private employee-to-employee message shown in the in-app inbox."""

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    body = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    sender = db.relationship("User", foreign_keys=[sender_id])
    recipient = db.relationship("User", foreign_keys=[recipient_id])


class BirthdayVoucher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    voucher_code = db.Column(db.String(120), nullable=True)
    voucher_filename = db.Column(db.String(255), nullable=True)
    sent_at = db.Column(db.DateTime, nullable=True)
