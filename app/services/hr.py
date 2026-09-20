"""Small, transaction-friendly HR domain helpers used by routes and scheduled checks."""

from datetime import date

from app.extensions import db
from app.models.hr import LeaveBalance, LeaveBalanceAdjustment, LeaveRequest, LeaveType, PublicHoliday
from app.models.user import EmployeeProfile, User


POLICY_DEFAULTS = {
    "ANNUAL": {"days": 22.0, "accrual": "monthly"},
    "SICK": {"days": 7.0, "accrual": "annual"},
    "MATERNITY": {"days": 84.0, "accrual": "event"},
    "PATERNITY": {"days": 3.0, "accrual": "event"},
    "LWP": {"days": 0.0, "accrual": "none"},
}


def calculate_working_days(start_date, end_date, public_holidays=()):
    """Count weekdays in an inclusive range, excluding applicable holidays."""
    holidays = set(public_holidays)
    days = 0
    current = start_date
    while current <= end_date:
        if current.weekday() < 5 and current not in holidays:
            days += 1
        current = current.fromordinal(current.toordinal() + 1)
    return days


def would_create_reporting_cycle(employee_user_id, proposed_manager_user_id):
    """Return true when assigning the manager would create a self/circular hierarchy."""
    if not proposed_manager_user_id or employee_user_id == proposed_manager_user_id:
        return bool(proposed_manager_user_id)

    visited = {employee_user_id}
    current_manager_id = proposed_manager_user_id
    while current_manager_id:
        if current_manager_id in visited:
            return True
        visited.add(current_manager_id)
        profile = EmployeeProfile.query.filter_by(user_id=current_manager_id).first()
        current_manager_id = profile.reporting_officer_id if profile else None
    return False


def deactivate_resigned_employees(today=None):
    """Disable sign-in after the effective resignation date while retaining history."""
    today = today or date.today()
    profiles = EmployeeProfile.query.filter(
        EmployeeProfile.resignation_date.isnot(None),
        EmployeeProfile.resignation_date <= today,
    ).all()
    changed = 0
    for profile in profiles:
        if profile.user.is_active:
            profile.user.is_active = False
            profile.employment_status = "resigned"
            changed += 1
    if changed:
        db.session.commit()
    return changed


def applicable_public_holidays(profile, start_date, end_date):
    """Return global and matching entity/location holidays for the employee period."""
    holidays = PublicHoliday.query.filter(
        PublicHoliday.is_active.is_(True),
        PublicHoliday.holiday_date.between(start_date, end_date),
    ).all()
    return {
        item.holiday_date
        for item in holidays
        if (item.location_id is None or item.location_id == profile.location_id)
        and (item.entity_id is None or item.entity_id == profile.entity_id)
    }


def leave_days_for_profile(profile, start_date, end_date):
    return calculate_working_days(
        start_date,
        end_date,
        applicable_public_holidays(profile, start_date, end_date),
    )


def _leave_code(leave_type):
    return leave_type.code or leave_type.name.upper().replace(" ", "_").replace("-", "_")


def entitlement_for_year(user, leave_type, calendar_year, today=None):
    """Apply policy entitlement with bounded joining and resignation pro-rating."""
    today = today or date.today()
    policy = POLICY_DEFAULTS.get(_leave_code(leave_type), {"days": leave_type.default_days, "accrual": leave_type.accrual_method})
    entitlement = float(policy["days"])
    profile = user.employee_profile
    if profile and _leave_code(leave_type) in {"ANNUAL", "SICK"}:
        # The existing policy accrues in calendar months.  Use that same convention
        # for joiners and leavers, rather than inventing a different daily rule.
        first_month = 1
        last_month = 12
        if profile.date_of_joining:
            if profile.date_of_joining.year > calendar_year:
                return 0.0
            if profile.date_of_joining.year == calendar_year:
                first_month = profile.date_of_joining.month
        if profile.resignation_date:
            if profile.resignation_date.year < calendar_year:
                return 0.0
            if profile.resignation_date.year == calendar_year:
                last_month = profile.resignation_date.month
        entitlement = round(entitlement * max(0, last_month - first_month + 1) / 12, 2)
    return entitlement


def get_or_create_leave_balance(user, leave_type, calendar_year=None, today=None):
    calendar_year = calendar_year or (today or date.today()).year
    balance = LeaveBalance.query.filter_by(
        user_id=user.id,
        leave_type_id=leave_type.id,
        calendar_year=calendar_year,
    ).first()
    if balance is None:
        balance = LeaveBalance(
            user_id=user.id,
            leave_type_id=leave_type.id,
            calendar_year=calendar_year,
            user=user,
            leave_type=leave_type,
        )
        db.session.add(balance)
    refresh_leave_balance(balance, today=today)
    return balance


def refresh_leave_balance(balance, today=None):
    """Derive the visible balance from entitlement, accrual, adjustments and approved leave."""
    today = today or date.today()
    leave_type = balance.leave_type
    code = _leave_code(leave_type)
    balance.entitled_days = entitlement_for_year(balance.user, leave_type, balance.calendar_year, today)

    if code == "ANNUAL":
        profile = balance.user.employee_profile
        months = today.month if today.year == balance.calendar_year else 12
        if profile and profile.date_of_joining and profile.date_of_joining.year == balance.calendar_year:
            months = max(0, months - profile.date_of_joining.month + 1)
        # Once an exit date is recorded the final, prorated entitlement is visible.
        # This intentionally allows a negative balance when approved leave exceeds it.
        if profile and profile.resignation_date and profile.resignation_date.year == balance.calendar_year:
            months = max(0, profile.resignation_date.month - (profile.date_of_joining.month if profile.date_of_joining and profile.date_of_joining.year == balance.calendar_year else 1) + 1)
        balance.accrued_days = min(balance.entitled_days, round(22.0 * months / 12, 2))
    elif leave_type.accrual_method in {"annual", "event"}:
        balance.accrued_days = balance.entitled_days
    else:
        balance.accrued_days = balance.entitled_days

    balance.utilized_days = round(sum(
        item.days for item in LeaveRequest.query.filter_by(
            user_id=balance.user_id,
            leave_type_id=balance.leave_type_id,
            status="approved",
            balance_applied=True,
        ).filter(LeaveRequest.start_date.between(date(balance.calendar_year, 1, 1), date(balance.calendar_year, 12, 31))).all()
    ), 2)
    balance.available_days = round(
        balance.accrued_days + balance.carry_forward_days + balance.adjustment_days - balance.utilized_days,
        2,
    )
    return balance


def rollover_leave_balances(calendar_year=None):
    """Create/recalculate the new-year Annual/Sick opening balances safely.

    Run this from a scheduled job in January. Re-running it is idempotent: the
    carry-forward value is derived from the preceding year and never added twice.
    """
    target_year = calendar_year or date.today().year
    previous_year = target_year - 1
    annual = LeaveType.query.filter_by(code="ANNUAL", is_active=True).first()
    sick = LeaveType.query.filter_by(code="SICK", is_active=True).first()
    if not annual and not sick:
        return 0
    changed = 0
    for profile in EmployeeProfile.query.join(EmployeeProfile.user).filter(User.is_active.is_(True)).all():
        for leave_type in (annual, sick):
            if leave_type is None:
                continue
            previous = get_or_create_leave_balance(profile.user, leave_type, previous_year, today=date(previous_year, 12, 31))
            current = get_or_create_leave_balance(profile.user, leave_type, target_year, today=date(target_year, 1, 1))
            expected_carry = min(max(previous.available_days, 0), 5.0) if leave_type.code == "ANNUAL" else 0.0
            if current.carry_forward_days != expected_carry:
                current.carry_forward_days = expected_carry
                refresh_leave_balance(current, today=date(target_year, 1, 1))
                changed += 1
    db.session.commit()
    return changed


def adjust_leave_balance(balance, days, reason, actor=None):
    """Record an adjustment instead of overwriting history, then recalculate the balance."""
    adjustment = LeaveBalanceAdjustment(
        leave_balance_id=balance.id,
        changed_by_id=actor.id if actor else None,
        days=days,
        reason=reason,
    )
    balance.adjustment_days = round(balance.adjustment_days + days, 2)
    db.session.add(adjustment)
    refresh_leave_balance(balance)
    return adjustment


def apply_approved_leave_balance(leave_request):
    """Idempotently mark an approval as applied and recalculate the relevant balance."""
    if leave_request.balance_applied:
        return None
    balance = get_or_create_leave_balance(
        leave_request.user,
        leave_request.leave_type,
        leave_request.start_date.year,
    )
    leave_request.balance_applied = True
    refresh_leave_balance(balance)
    return balance


def restore_cancelled_leave_balance(leave_request):
    """Reverse the applied marker only after cancellation is approved, preserving the request."""
    if not leave_request.balance_applied:
        return None
    leave_request.balance_applied = False
    balance = get_or_create_leave_balance(
        leave_request.user,
        leave_request.leave_type,
        leave_request.start_date.year,
    )
    refresh_leave_balance(balance)
    return balance
