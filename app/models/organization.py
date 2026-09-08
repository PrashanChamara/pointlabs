from app.extensions import db


class NamedRecord(db.Model):
    __abstract__ = True

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)


class Entity(NamedRecord):
    legal_name = db.Column(db.String(180), nullable=True)
    country_code = db.Column(db.String(2), nullable=True)
    currency = db.Column(db.String(3), nullable=True)
    address = db.Column(db.Text, nullable=True)


class Location(NamedRecord):
    entity_id = db.Column(db.Integer, db.ForeignKey("entity.id"), nullable=True)
    country_code = db.Column(db.String(2), nullable=True)
    entity = db.relationship("Entity")


class Department(NamedRecord):
    pass


class Designation(NamedRecord):
    is_reporting_officer_designation = db.Column(
        db.Boolean, nullable=False, default=False
    )
