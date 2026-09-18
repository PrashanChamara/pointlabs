from flask import g, has_app_context

from app.extensions import db
from app.models.organization import Department, Designation, Entity, Location
from app.models.user import EmployeeProfile, User
from app.services.seed import seed_reference_data


def sign_in(client, user):
    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)
        session["_fresh"] = True
    if has_app_context():
        g.pop("_login_user", None)


def make_user(username, *, designation=None, entity=None):
    user = User(username=username, email=f"{username}@example.test", must_change_password=False)
    user.set_password("password")
    db.session.add(user)
    db.session.flush()
    db.session.add(EmployeeProfile(
        user_id=user.id,
        full_name=username.replace("-", " ").title(),
        phone="+971500000000",
        designation_id=designation.id if designation else None,
        entity_id=entity.id if entity else None,
    ))
    db.session.flush()
    return user


def test_employee_can_remove_their_profile_photo(client, app):
    with app.app_context():
        user = make_user("photo-removal")
        profile = user.employee_profile
        profile.profile_photo_stored_path = "profile-photo.webp"
        profile.profile_photo_filename = "profile-photo.webp"
        profile.profile_photo_mime_type = "image/webp"
        db.session.commit()
        sign_in(client, user)

    response = client.post("/profile", data={"action": "remove_photo"})

    assert response.status_code == 302
    with app.app_context():
        profile = User.query.filter_by(username="photo-removal").one().employee_profile
        assert profile.profile_photo_stored_path is None
        assert profile.profile_photo_filename is None
        assert profile.profile_photo_mime_type is None
    response = client.get("/profile")
    assert b"Add photo" in response.data


def test_configuration_admin_can_edit_entity_location_and_department(client, app):
    with app.app_context():
        seed_reference_data("admin123")
        admin = User.query.filter_by(username="admin").one()
        entity = Entity(name="Pointlabs UAE", legal_name="Pointlabs Technologies Ltd", country_code="AE", currency="AED")
        department = Department(name="Platform")
        db.session.add_all((entity, department))
        db.session.flush()
        location = Location(name="Dubai", entity_id=entity.id, country_code="AE")
        db.session.add(location)
        db.session.commit()
        entity_id, department_id, location_id = entity.id, department.id, location.id
        sign_in(client, admin)

    response = client.get("/admin/master-data/entities")
    assert response.status_code == 200
    assert b"Add entity" in response.data
    assert client.post(f"/admin/master-data/entities/{entity_id}/edit", data={
        "name": "Pointlabs Dubai", "legal_name": "Pointlabs Technologies Ltd", "country_code": "AE", "currency": "AED", "address": "Dubai Internet City",
    }).status_code == 302
    assert client.post(f"/admin/master-data/departments/{department_id}/edit", data={"name": "Platform Engineering"}).status_code == 302
    assert client.post(f"/admin/master-data/locations/{location_id}/edit", data={"name": "Dubai HQ", "entity_id": entity_id, "country_code": "AE"}).status_code == 302

    with app.app_context():
        assert db.session.get(Entity, entity_id).name == "Pointlabs Dubai"
        assert db.session.get(Entity, entity_id).address == "Dubai Internet City"
        assert db.session.get(Department, department_id).name == "Platform Engineering"
        assert db.session.get(Location, location_id).name == "Dubai HQ"


def test_yellow_pages_is_contact_only_and_attendance_is_hidden_for_employee(client, app):
    with app.app_context():
        entity = Entity(name="Pointlabs Sri Lanka")
        manager_title = Designation(name="Engineering Manager", is_reporting_officer_designation=True)
        db.session.add_all((entity, manager_title))
        db.session.flush()
        employee = make_user("amina-perera", entity=entity)
        make_user("mila-manager", designation=manager_title, entity=entity)
        db.session.commit()
        sign_in(client, employee)

    response = client.get("/yellow-pages?q=Amina")

    assert response.status_code == 200
    assert b"Amina Perera" in response.data
    assert b"Pointlabs Sri Lanka" in response.data
    assert b"Employee Code" not in response.data
    assert b"Export" not in response.data
    response = client.get("/")
    assert b"Yellow Pages" in response.data
    assert b">Attendance<" not in response.data



def test_attendance_remains_visible_for_manager(client, app):
    with app.app_context():
        manager_title = Designation(name="People Manager", is_reporting_officer_designation=True)
        db.session.add(manager_title)
        db.session.flush()
        manager = make_user("attendance-manager", designation=manager_title)
        db.session.commit()
        sign_in(client, manager)

    response = client.get("/")

    assert b"Yellow Pages" in response.data
    assert b">Attendance<" in response.data
