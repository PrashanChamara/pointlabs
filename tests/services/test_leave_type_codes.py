"""Regression coverage for canonical leave-type identifiers."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import sqlalchemy as sa

from app.extensions import db
from app.models.hr import LeaveType
from app.models.user import User
from app.services.seed import seed_reference_data


STANDARD_CODES = {
    "Annual Leave": "ANNUAL",
    "Sick Leave": "SICK",
    "Paternity Leave": "PATERNITY",
    "Maternity Leave": "MATERNITY",
    "Compassionate Leave": "COMPASSIONATE",
    "Off in Lieu": "OFF_IN_LIEU",
    "WFH": "WFH",
    "Leave Without Pay": "LWP",
}


def _leave_code_migration():
    path = Path(__file__).parents[2] / "migrations/versions/ac19c777da37_backfill_leave_type_codes.py"
    spec = spec_from_file_location("backfill_leave_type_codes", path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_leave_code_migration_backfills_blank_values_without_overwriting_custom_codes(monkeypatch):
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    leave_type = sa.Table(
        "leave_type",
        metadata,
        sa.Column("name", sa.String(80), primary_key=True),
        sa.Column("code", sa.String(30)),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            leave_type.insert(),
            [
                {"name": "Annual Leave", "code": "ORG_ANNUAL"},
                {"name": "Sick Leave", "code": ""},
                {"name": "Paternity Leave", "code": "   "},
                {"name": "Maternity Leave", "code": None},
                {"name": "Compassionate Leave", "code": None},
                {"name": "Off in Lieu", "code": None},
                {"name": "WFH", "code": None},
                {"name": "Leave Without Pay", "code": None},
            ],
        )
        migration = _leave_code_migration()
        monkeypatch.setattr(migration.op, "get_bind", lambda: connection)
        migration.upgrade()
        rows = dict(connection.execute(sa.select(leave_type.c.name, leave_type.c.code)).all())

    assert rows["Annual Leave"] == "ORG_ANNUAL"
    assert {name: rows[name] for name in STANDARD_CODES if name != "Annual Leave"} == {
        name: code for name, code in STANDARD_CODES.items() if name != "Annual Leave"
    }


def test_seed_keeps_existing_custom_code_and_is_repeatable(app):
    with app.app_context():
        db.session.add(LeaveType(name="Annual Leave", code="COMPANY_ANNUAL", default_days=18))
        db.session.commit()

        seed_reference_data("admin123")
        seed_reference_data("admin123")

        leave_types = {leave_type.name: leave_type for leave_type in LeaveType.query.all()}
        assert leave_types["Annual Leave"].code == "COMPANY_ANNUAL"
        for name, code in STANDARD_CODES.items():
            if name != "Annual Leave":
                assert leave_types[name].code == code
        assert LeaveType.query.filter(LeaveType.name.in_(STANDARD_CODES)).count() == len(STANDARD_CODES)


def test_fresh_seed_creates_all_canonical_leave_type_codes(app):
    with app.app_context():
        seed_reference_data("admin123")

        leave_type_codes = {
            leave_type.name: leave_type.code
            for leave_type in LeaveType.query.filter(LeaveType.name.in_(STANDARD_CODES)).all()
        }

    assert leave_type_codes == STANDARD_CODES


def test_seeded_annual_and_sick_codes_render_balance_cards(client, app):
    with app.app_context():
        seed_reference_data("admin123")
        user = User.query.filter_by(username="admin").one()
        user.must_change_password = False
        db.session.commit()
        user_id = user.id

    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True

    response = client.get("/leave")

    assert response.status_code == 200
    assert b"Annual Leave" in response.data
    assert b"Sick Leave" in response.data
