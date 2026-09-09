from datetime import date, timedelta

from app.extensions import db
from app.models.hr import ComplianceReminder, Notification
from app.models.user import EmployeeProfile, User
from app.services.compliance import process_expiry_reminders
from app.services.seed import seed_reference_data


def test_expiring_identity_document_notifies_once_to_employee_and_hr(app):
    with app.app_context():
        seed_reference_data("admin123")
        employee = User(username="expiry-user", must_change_password=False); employee.set_password("password")
        db.session.add(employee); db.session.flush()
        day = date(2026, 10, 1)
        db.session.add(EmployeeProfile(user_id=employee.id, full_name="Expiry User", passport_expiry_date=day + timedelta(days=30)))
        db.session.commit()
        assert process_expiry_reminders(today=day) == 1
        assert process_expiry_reminders(today=day) == 0
        assert ComplianceReminder.query.one().document_kind == "Passport"
        assert Notification.query.filter(Notification.message.contains("Passport expires in 30 days")).count() == 2
