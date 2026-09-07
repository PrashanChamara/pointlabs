from app.extensions import db
from app.models.user import User
import re


def test_temporary_admin_is_redirected_to_password_change(client, app):
    with app.app_context():
        user = User(username="admin", must_change_password=True)
        user.set_password("admin123")
        db.session.add(user)
        db.session.commit()
    response = client.post("/auth/login", data={"username": "admin", "password": "admin123"})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/change-password")


def test_invalid_login_keeps_the_branded_sign_in_experience(client):
    response = client.post("/auth/login", data={"username": "admin", "password": "incorrect"})

    assert response.status_code == 401
    assert b"login-layout" in response.data
    assert b"We couldn't sign you in." in response.data
    assert b'value="admin"' in response.data
    assert b"Invalid credentials" not in response.data


def test_login_form_has_a_csrf_token_and_accepts_it_when_enabled(client, app):
    app.config["WTF_CSRF_ENABLED"] = True
    with app.app_context():
        user = User(username="admin", must_change_password=False)
        user.set_password("admin123")
        db.session.add(user)
        db.session.commit()
    page = client.get("/auth/login")
    assert b"login-layout" in page.data
    assert b"brand-mark" not in page.data
    token = re.search(rb'name="csrf_token" value="([^"]+)"', page.data).group(1).decode()
    response = client.post("/auth/login", data={"username": "admin", "password": "admin123", "csrf_token": token})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
