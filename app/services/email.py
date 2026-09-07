import smtplib
from email.message import EmailMessage
from flask import current_app


def send_email(to_address, subject, body):
    config = current_app.config
    if not all([config.get("SMTP_HOST"), config.get("SMTP_FROM")]):
        current_app.logger.warning("Email not sent; SMTP is not configured: %s", subject)
        return False
    message = EmailMessage(); message["From"] = config["SMTP_FROM"]; message["To"] = to_address; message["Subject"] = subject; message.set_content(body)
    with smtplib.SMTP(config["SMTP_HOST"], config["SMTP_PORT"]) as smtp:
        smtp.starttls()
        if config.get("SMTP_USERNAME"): smtp.login(config["SMTP_USERNAME"], config.get("SMTP_PASSWORD", ""))
        smtp.send_message(message)
    return True
