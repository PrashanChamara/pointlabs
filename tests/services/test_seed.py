from app.extensions import db
from app.models.organization import Designation
from app.models.user import User
from app.services.seed import seed_reference_data


def test_seed_creates_reference_designations_and_admin(app):
    with app.app_context():
        seed_reference_data("admin123")
        assert Designation.query.count() == 33
        assert Designation.query.filter_by(is_reporting_officer_designation=True).count() == 11
        admin = User.query.filter_by(username="admin").one()
        assert admin.must_change_password and admin.check_password("admin123")
        db.session.remove()
