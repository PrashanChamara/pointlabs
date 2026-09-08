from datetime import date

from app.services.hr import calculate_working_days, would_create_reporting_cycle


def test_leave_days_exclude_weekends_and_configured_public_holidays():
    assert calculate_working_days(
        date(2026, 9, 4),
        date(2026, 9, 8),
        {date(2026, 9, 7)},
    ) == 2


def test_reporting_relationship_cannot_become_a_cycle(app):
    from app.extensions import db
    from app.models.user import EmployeeProfile, User

    with app.app_context():
        manager = User(username="manager", must_change_password=False)
        employee = User(username="employee", must_change_password=False)
        manager.set_password("password")
        employee.set_password("password")
        db.session.add_all([manager, employee])
        db.session.flush()
        db.session.add_all([
            EmployeeProfile(user_id=manager.id, full_name="Manager"),
            EmployeeProfile(user_id=employee.id, full_name="Employee", reporting_officer_id=manager.id),
        ])
        db.session.commit()

        assert would_create_reporting_cycle(manager.id, employee.id) is True
        assert would_create_reporting_cycle(employee.id, manager.id) is False
