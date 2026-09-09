"""Scheduled credential-expiry notifications for HR and affected employees."""
from datetime import date

from app.extensions import db
from app.models.hr import ComplianceReminder, Notification
from app.models.user import EmployeeProfile, User


def process_expiry_reminders(today=None, thresholds=(90, 60, 30, 7, 0)):
    today = today or date.today()
    delivered = 0
    hr_users = [user for user in User.query.filter_by(is_active=True).all() if user.has_hr_access]
    for profile in EmployeeProfile.query.join(User, EmployeeProfile.user_id == User.id).filter(User.is_active.is_(True)).all():
        for document_kind, expiry_date in (("Passport", profile.passport_expiry_date), ("Emirates ID", profile.emirates_id_expiry_date)):
            if not expiry_date:
                continue
            days = (expiry_date - today).days
            if days not in thresholds:
                continue
            if ComplianceReminder.query.filter_by(user_id=profile.user_id, document_kind=document_kind, expiry_date=expiry_date, threshold_days=days).first():
                continue
            wording = f"{document_kind} expires {'today' if days == 0 else f'in {days} days'} ({expiry_date:%d %b %Y})."
            db.session.add(ComplianceReminder(user_id=profile.user_id, document_kind=document_kind, expiry_date=expiry_date, threshold_days=days))
            db.session.add(Notification(user_id=profile.user_id, message=f"Compliance reminder: your {wording}"))
            for hr_user in hr_users:
                if hr_user.id != profile.user_id:
                    db.session.add(Notification(user_id=hr_user.id, message=f"Compliance reminder for {profile.full_name}: {wording}"))
            delivered += 1
    db.session.commit()
    return delivered
