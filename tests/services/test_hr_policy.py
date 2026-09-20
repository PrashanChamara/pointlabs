from datetime import date

from app.services.hr import (
    calculate_working_days, get_or_create_leave_balance, rollover_leave_balances,
    would_create_reporting_cycle,
)


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


def test_resignation_prorates_annual_and_sick_and_keeps_negative_balance(app):
    from app.extensions import db
    from app.models.hr import LeaveRequest, LeaveType
    from app.models.user import EmployeeProfile, User

    with app.app_context():
        user = User(username="leaver", must_change_password=False)
        user.set_password("password")
        db.session.add(user); db.session.flush()
        db.session.add(EmployeeProfile(
            user_id=user.id, full_name="Leaving Employee", date_of_joining=date(2024, 1, 1),
            resignation_date=date(2026, 3, 20),
        ))
        annual = LeaveType(name="Annual Leave", code="ANNUAL", default_days=22, accrual_method="monthly")
        sick = LeaveType(name="Sick Leave", code="SICK", default_days=7, accrual_method="annual")
        db.session.add_all((annual, sick)); db.session.flush()
        db.session.add(LeaveRequest(user_id=user.id, leave_type_id=annual.id, start_date=date(2026, 2, 2), end_date=date(2026, 2, 13), days=10, status="approved", balance_applied=True))
        db.session.commit()

        annual_balance = get_or_create_leave_balance(user, annual, 2026, today=date(2026, 2, 1))
        sick_balance = get_or_create_leave_balance(user, sick, 2026, today=date(2026, 2, 1))
        assert annual_balance.entitled_days == 5.5
        assert annual_balance.available_days == -4.5
        assert sick_balance.entitled_days == 1.75


def test_annual_rollover_caps_carry_forward_and_sick_expires(app):
    from app.extensions import db
    from app.models.hr import LeaveType
    from app.models.user import EmployeeProfile, User

    with app.app_context():
        user = User(username="rollover", must_change_password=False)
        user.set_password("password")
        db.session.add(user); db.session.flush()
        db.session.add(EmployeeProfile(user_id=user.id, full_name="Rollover Employee", date_of_joining=date(2024, 1, 1)))
        annual = LeaveType(name="Annual Leave", code="ANNUAL", default_days=22, accrual_method="monthly")
        sick = LeaveType(name="Sick Leave", code="SICK", default_days=7, accrual_method="annual")
        db.session.add_all((annual, sick)); db.session.flush(); db.session.commit()
        annual_previous = get_or_create_leave_balance(user, annual, 2025, today=date(2025, 12, 31))
        sick_previous = get_or_create_leave_balance(user, sick, 2025, today=date(2025, 12, 31))
        annual_previous.adjustment_days = 4
        sick_previous.adjustment_days = 3
        db.session.commit()

        rollover_leave_balances(2026)
        rollover_leave_balances(2026)
        annual_current = get_or_create_leave_balance(user, annual, 2026, today=date(2026, 1, 1))
        sick_current = get_or_create_leave_balance(user, sick, 2026, today=date(2026, 1, 1))
        assert annual_current.carry_forward_days == 5
        assert sick_current.carry_forward_days == 0
