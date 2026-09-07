from app.services.email import (
    send_birthday_email,
    send_leave_status_email,
    send_message_email,
    send_password_reset_email,
)


class FakeSMTP:
    sent = []

    def __init__(self, *args):
        self.args = args

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def starttls(self):
        return None

    def login(self, username, password):
        self.login_details = (username, password)

    def send_message(self, message):
        self.sent.append(message)


def test_password_reset_email_uses_branded_html_layout(app, monkeypatch):
    monkeypatch.setattr("app.services.email.smtplib.SMTP", FakeSMTP)
    FakeSMTP.sent.clear()
    app.config.update(SMTP_HOST="smtp.example.test", SMTP_FROM="hello@example.test", SMTP_USERNAME="user", SMTP_PASSWORD="secret")
    with app.app_context():
        assert send_password_reset_email("person@example.test", "814590")
    message = FakeSMTP.sent[0]
    html = message.get_body(preferencelist=("html",)).get_content()
    assert "Pointlabs One" in html
    assert "814590" in html
    assert "cid:pointlabs-ring" in html
    assert "Pointlabs One password reset" in message["Subject"]


def test_all_transactional_email_types_render_branded_content(app, monkeypatch):
    monkeypatch.setattr("app.services.email.smtplib.SMTP", FakeSMTP)
    FakeSMTP.sent.clear()
    app.config.update(SMTP_HOST="smtp.example.test", SMTP_FROM="hello@example.test")
    with app.app_context():
        assert send_leave_status_email("person@example.test", "Mira Patel", "Annual Leave", "approved", "Enjoy your time away.")
        assert send_message_email("person@example.test", "Mira Patel", "Welcome to the team.")
        assert send_birthday_email("person@example.test", "Mira Patel", "PL-BDAY-2026")
    rendered = [message.get_body(preferencelist=("html",)).get_content() for message in FakeSMTP.sent]
    assert all("Pointlabs One" in html and "cid:pointlabs-ring" in html for html in rendered)
    assert "Annual Leave" in rendered[0]
    assert "Welcome to the team." in rendered[1]
    assert "PL-BDAY-2026" in rendered[2]
