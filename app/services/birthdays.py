from datetime import date, timedelta
from app.extensions import db
from app.models.hr import BirthdayEmailSettings, BirthdayVoucher, Notification
from app.models.user import EmployeeProfile, User
from app.services.email import send_birthday_email


def process_birthdays(today=None):
    today = today or date.today()
    admins = User.query.filter_by(is_administrator=True).all()
    settings = BirthdayEmailSettings.query.order_by(BirthdayEmailSettings.id).first()
    attachment = None
    if settings and settings.attachment_stored_path:
        from pathlib import Path
        from flask import current_app
        attachment = [(Path(current_app.instance_path) / "uploads" / settings.attachment_stored_path,
                       settings.attachment_filename or "Pointlabs-celebration", settings.attachment_mime_type or "application/pdf")]
    for profile in EmployeeProfile.query.filter(EmployeeProfile.date_of_birth.isnot(None)).all():
        birthday = profile.date_of_birth.replace(year=today.year)
        if birthday == today + timedelta(days=3):
            for admin in admins:
                db.session.add(Notification(user_id=admin.id, message=f"Upcoming birthday: {profile.full_name} on {birthday:%d %b}."))
        if birthday == today and profile.user.email:
            voucher = BirthdayVoucher.query.filter_by(user_id=profile.user_id).first()
            if send_birthday_email(profile.user.email, profile.full_name, voucher.voucher_code if voucher else None,
                                   subject=settings.subject if settings else None,
                                   message=settings.message if settings else None,
                                   attachments=attachment):
                if voucher: voucher.sent_at = __import__('datetime').datetime.utcnow()
    db.session.commit()
