from datetime import date, timedelta
from app.extensions import db
from app.models.hr import BirthdayVoucher, Notification
from app.models.user import EmployeeProfile, User
from app.services.email import send_email


def process_birthdays(today=None):
    today = today or date.today()
    admins = User.query.filter_by(is_administrator=True).all()
    for profile in EmployeeProfile.query.filter(EmployeeProfile.date_of_birth.isnot(None)).all():
        birthday = profile.date_of_birth.replace(year=today.year)
        if birthday == today + timedelta(days=3):
            for admin in admins:
                db.session.add(Notification(user_id=admin.id, message=f"Upcoming birthday: {profile.full_name} on {birthday:%d %b}."))
        if birthday == today and profile.user.email:
            voucher = BirthdayVoucher.query.filter_by(user_id=profile.user_id).first()
            extra = f"\nGift voucher code: {voucher.voucher_code}" if voucher and voucher.voucher_code else ""
            if send_email(profile.user.email, "Happy Birthday from Pointlabs", f"Happy Birthday, {profile.full_name}!{extra}"):
                if voucher: voucher.sent_at = __import__('datetime').datetime.utcnow()
    db.session.commit()
