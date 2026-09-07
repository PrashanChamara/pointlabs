from app.extensions import db
from app.models.organization import Designation


def test_designation_has_editable_reporting_officer_flag(app):
    with app.app_context():
        db.create_all()
        designation = Designation(
            name="Head of Engineering", is_reporting_officer_designation=True
        )
        db.session.add(designation)
        db.session.commit()

        assert designation.is_reporting_officer_designation is True
