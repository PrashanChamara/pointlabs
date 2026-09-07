from datetime import datetime
from app.extensions import db


class LeaveType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    default_days = db.Column(db.Float, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)


class LeaveBalance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    leave_type_id = db.Column(db.Integer, db.ForeignKey("leave_type.id"), nullable=False)
    available_days = db.Column(db.Float, nullable=False, default=0)
    user = db.relationship("User")
    leave_type = db.relationship("LeaveType")


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
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    user = db.relationship("User", foreign_keys=[user_id])
    leave_type = db.relationship("LeaveType")


class EmployeeDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class BirthdayVoucher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    voucher_code = db.Column(db.String(120), nullable=True)
    voucher_filename = db.Column(db.String(255), nullable=True)
    sent_at = db.Column(db.DateTime, nullable=True)
