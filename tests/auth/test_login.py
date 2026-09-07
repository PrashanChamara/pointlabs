from app.extensions import db
from app.models.user import User


def test_temporary_admin_is_redirected_to_password_change(client, app):
    with app.app_context():
        user = User(username="admin", must_change_password=True)
        user.set_password("admin123")
        db.session.add(user)
        db.session.commit()
    response = client.post("/auth/login", data={"username": "admin", "password": "admin123"})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/change-password")
