from app.models.user import User


def test_user_requires_password_change_when_seeded():
    user = User(username="admin", must_change_password=True)
    user.set_password("temporary-password")

    assert user.check_password("temporary-password")
    assert user.must_change_password is True
