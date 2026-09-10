from app.extensions import db
from app.models.user import PasswordResetCode, User
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


def test_login_accepts_registered_email_as_user_id(client, app):
    with app.app_context():
        user = User(
            username="admin",
            email="owner@pointlabs.example",
            must_change_password=False,
        )
        user.set_password("personal-password")
        db.session.add(user)
        db.session.commit()

    response = client.post(
        "/auth/login",
        data={
            "username": "OWNER@pointlabs.example ",
            "password": "personal-password",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_authentication_forms_explain_that_registered_email_is_accepted(client):
    assert b"User ID or registered email" in client.get("/auth/login").data
    assert b"User ID or registered email" in client.get("/auth/forgot-password").data


def test_fresh_otp_can_reset_password_using_registered_email(client, app, monkeypatch):
    monkeypatch.setattr("app.auth.routes.send_password_reset_email", lambda *_: True)
    with app.app_context():
        user = User(
            username="admin",
            email="owner@pointlabs.example",
            must_change_password=False,
        )
        user.set_password("old-password")
        db.session.add(user)
        db.session.commit()

    response = client.post(
        "/auth/forgot-password",
        data={"username": "owner@pointlabs.example", "email": "owner@pointlabs.example"},
    )
    assert response.status_code == 302

    with app.app_context():
        reset_code = PasswordResetCode.query.one().code

    response = client.post(
        "/auth/reset-password",
        data={
            "username": "owner@pointlabs.example",
            "code": reset_code,
            "new_password": "new-personal-password",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")
    with app.app_context():
        assert User.query.filter_by(username="admin").one().check_password("new-personal-password")


def test_invalid_otp_keeps_the_branded_reset_experience(client, app):
    with app.app_context():
        user = User(
            username="admin",
            email="owner@pointlabs.example",
            must_change_password=False,
        )
        user.set_password("old-password")
        db.session.add(user)
        db.session.commit()

    response = client.post(
        "/auth/reset-password",
        data={
            "username": "owner@pointlabs.example",
            "code": "000000",
            "new_password": "new-personal-password",
        },
    )

    assert response.status_code == 400
    assert b"auth-card" in response.data
    assert b"login-alert" in response.data


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
    assert b"logo-light.png" not in page.data
    assert b'class="login-brand-product"><b>O</b>ne</span>' in page.data
    token = re.search(rb'name="csrf_token" value="([^"]+)"', page.data).group(1).decode()
    response = client.post("/auth/login", data={"username": "admin", "password": "admin123", "csrf_token": token})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_root_service_worker_is_available_for_the_installed_app(client):
    response = client.get("/service-worker.js")

    assert response.status_code == 200
    assert response.mimetype == "application/javascript"
    assert response.headers["Service-Worker-Allowed"] == "/"
    assert b"pointlabs-shell" in response.data
