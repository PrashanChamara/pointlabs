from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import date, datetime

from app.extensions import db


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    must_change_password = db.Column(db.Boolean, nullable=False, default=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_administrator = db.Column(db.Boolean, nullable=False, default=False)
    role = db.Column(db.String(20), nullable=False, default="employee", index=True)
    email = db.Column(db.String(255), unique=True, nullable=True)

    @property
    def has_hr_access(self):
        return self.is_administrator or self.role in {"admin", "hr"}

    @property
    def can_approve_leave(self):
        return self.has_hr_access or bool(getattr(self, "direct_reports", []))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class EmployeeProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    employee_code = db.Column(db.String(80), unique=True, nullable=True)
    full_name = db.Column(db.String(160), nullable=False, default="")
    preferred_name = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(40), nullable=True)
    address = db.Column(db.Text, nullable=True)
    current_address = db.Column(db.Text, nullable=True)
    permanent_address = db.Column(db.Text, nullable=True)
    home_country_contact_number = db.Column(db.String(40), nullable=True)
    personal_email = db.Column(db.String(255), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    date_of_joining = db.Column(db.Date, nullable=True)
    probation_end_date = db.Column(db.Date, nullable=True)
    resignation_date = db.Column(db.Date, nullable=True, index=True)
    employment_status = db.Column(db.String(30), nullable=False, default="active", index=True)
    employment_type = db.Column(db.String(80), nullable=True)
    gender = db.Column(db.String(30), nullable=True)
    nationality = db.Column(db.String(80), nullable=True)
    marital_status = db.Column(db.String(40), nullable=True)
    national_identity_card_number = db.Column(db.String(100), nullable=True)
    emirates_id_number = db.Column(db.String(100), nullable=True)
    emirates_id_expiry_date = db.Column(db.Date, nullable=True)
    passport_number = db.Column(db.String(100), nullable=True)
    passport_expiry_date = db.Column(db.Date, nullable=True)
    emergency_contact_name = db.Column(db.String(160), nullable=True)
    emergency_contact_number = db.Column(db.String(40), nullable=True)
    emergency_contact_relationship = db.Column(db.String(80), nullable=True)
    account_holder_name = db.Column(db.String(160), nullable=True)
    bank_name = db.Column(db.String(160), nullable=True)
    branch_name = db.Column(db.String(160), nullable=True)
    bank_account_number = db.Column(db.String(160), nullable=True)
    swift_code = db.Column(db.String(80), nullable=True)
    ifsc_code = db.Column(db.String(80), nullable=True)
    bank_address = db.Column(db.Text, nullable=True)
    bank_currency = db.Column(db.String(3), nullable=True)
    entity_id = db.Column(db.Integer, db.ForeignKey("entity.id"), nullable=True)
    location_id = db.Column(db.Integer, db.ForeignKey("location.id"), nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), nullable=True)
    designation_id = db.Column(db.Integer, db.ForeignKey("designation.id"), nullable=True)
    reporting_officer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    user = db.relationship("User", foreign_keys=[user_id], backref=db.backref("employee_profile", uselist=False))
    designation = db.relationship("Designation")
    department = db.relationship("Department")
    location = db.relationship("Location")
    entity = db.relationship("Entity")
    reporting_officer = db.relationship("User", foreign_keys=[reporting_officer_id], backref="direct_reports")

    @property
    def is_resigned_effective(self):
        return bool(self.resignation_date and self.resignation_date <= date.today())


class PasswordResetCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    code = db.Column(db.String(12), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
