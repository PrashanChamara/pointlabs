from datetime import date

from app.extensions import db
from app.models.user import EmployeeProfile, User
from app.services.seed import seed_reference_data


def sign_in(client, user):
    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)
        session["_fresh"] = True


def make_employee(app):
    with app.app_context():
        employee = User(username="mira", email="mira@example.test", must_change_password=False)
        employee.set_password("password")
        db.session.add(employee)
        db.session.flush()
        db.session.add(EmployeeProfile(user_id=employee.id, full_name="Mira Patel", date_of_joining=date(2025, 1, 1)))
        db.session.commit()
        return employee.id


def test_employee_can_submit_an_other_hr_request(client, app):
    employee_id = make_employee(app)
    with app.app_context():
        sign_in(client, db.session.get(User, employee_id))
    response = client.post("/requests", data={"category": "Salary Certificate", "details": "Needed for a bank application."})
    assert response.status_code == 302
    with app.app_context():
        from app.models.hr import OtherRequest
        assert OtherRequest.query.one().user_id == employee_id


def test_hr_can_create_compensation_and_generate_an_employee_payslip(client, app):
    with app.app_context():
        seed_reference_data("admin123")
        admin = User.query.filter_by(username="admin").one()
        sign_in(client, admin)
    employee_id = make_employee(app)
    response = client.post(f"/admin/payroll/compensation/{employee_id}", data={
        "effective_date": "2026-09-01", "currency": "LKR", "basic_salary": "100000", "allowances": "10000", "other_earnings": "0", "wht": "0", "epf": "8000", "etf": "0", "paye": "0", "other_deductions": "0",
    })
    assert response.status_code == 302
    response = client.post(f"/admin/payroll/generate/{employee_id}", data={"year": "2026", "month": "9"})
    assert response.status_code == 302
    with app.app_context():
        from app.models.hr import Payslip
        assert Payslip.query.one().net_salary == 102000
