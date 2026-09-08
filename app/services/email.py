"""Branded email delivery for Pointlabs One transactional workflows."""

from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
import smtplib

from flask import current_app, render_template


def send_email(to_address, subject, body, template_name="emails/notice.html", attachments=None, **context):
    """Deliver a branded HTML message with a readable plain-text alternative."""
    config = current_app.config
    if not all([config.get("SMTP_HOST"), config.get("SMTP_FROM")]):
        current_app.logger.warning("Email not sent; SMTP is not configured: %s", subject)
        return False

    html = render_template(
        template_name,
        subject=subject,
        body=body,
        preheader=context.pop("preheader", subject),
        **context,
    )
    message = EmailMessage()
    message["From"] = formataddr(("Pointlabs One", config["SMTP_FROM"]))
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(body)
    message.add_alternative(html, subtype="html")

    ring = Path(current_app.static_folder) / "images" / "pointlabs-ring.png"
    if ring.is_file():
        message.get_payload()[-1].add_related(
            ring.read_bytes(),
            maintype="image",
            subtype="png",
            cid="<pointlabs-ring>",
            filename="pointlabs-ring.png",
            disposition="inline",
        )

    for attachment in attachments or []:
        path, filename, mime_type = attachment
        try:
            payload = Path(path).read_bytes()
            maintype, subtype = mime_type.split("/", 1)
        except (OSError, ValueError):
            current_app.logger.exception("Pointlabs One email attachment could not be read: %s", filename)
            return False
        message.add_attachment(payload, maintype=maintype, subtype=subtype, filename=filename)

    try:
        with smtplib.SMTP(config["SMTP_HOST"], config["SMTP_PORT"]) as smtp:
            smtp.starttls()
            if config.get("SMTP_USERNAME"):
                smtp.login(config["SMTP_USERNAME"], config.get("SMTP_PASSWORD", ""))
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException):
        current_app.logger.exception("Pointlabs One email delivery failed: %s", subject)
        return False
    return True


def send_password_reset_email(to_address, code):
    return send_email(
        to_address,
        "Pointlabs One password reset",
        f"Your Pointlabs One verification code is {code}. It expires in 15 minutes.",
        "emails/password_reset.html",
        code=code,
        preheader="Use this secure code to reset your password.",
    )


def send_leave_status_email(to_address, employee_name, leave_type, status, comment=None):
    message = f"{employee_name}'s {leave_type} leave request was {status}."
    if comment:
        message += f" Note: {comment}"
    return send_email(
        to_address,
        f"Pointlabs One · Leave {status}",
        message,
        "emails/leave_status.html",
        employee_name=employee_name,
        leave_type=leave_type,
        status=status,
        comment=comment,
        preheader=f"Leave request {status}.",
    )


def send_message_email(to_address, sender_name, message_body):
    return send_email(
        to_address,
        "Pointlabs One · New message",
        f"{sender_name} sent you a message in Pointlabs One.\n\n{message_body}",
        "emails/new_message.html",
        sender_name=sender_name,
        message_body=message_body,
        preheader=f"New message from {sender_name}.",
    )


def send_birthday_email(to_address, employee_name, voucher_code=None):
    plain = f"Happy Birthday, {employee_name}!"
    if voucher_code:
        plain += f" Your gift voucher code is {voucher_code}."
    return send_email(
        to_address,
        "Happy Birthday from Pointlabs",
        plain,
        "emails/birthday.html",
        employee_name=employee_name,
        voucher_code=voucher_code,
        preheader=f"A birthday celebration from the Pointlabs team.",
    )


def send_notice_email(to_address, subject, body, preheader=None):
    """Use the shared branded layout for HR requests, documents and payslip notices."""
    return send_email(
        to_address,
        subject,
        body,
        "emails/notice.html",
        preheader=preheader or subject,
    )


def send_payslip_email(to_address, employee_name, payroll_period, pdf_path, filename):
    """Deliver a confidential payslip only after its private PDF exists."""
    return send_email(
        to_address,
        f"Your Pointlabs Payslip – {payroll_period}",
        f"Hello {employee_name},\n\nYour {payroll_period} payslip is available. "
        "This is a confidential document; please keep it secure. A PDF copy is attached.",
        "emails/notice.html",
        preheader=f"Your confidential {payroll_period} payslip is attached.",
        attachments=[(pdf_path, filename, "application/pdf")],
    )


def send_leave_confirmation_email(to_address, employee_name, leave_type, leave_dates, pdf_path, filename):
    """Deliver an approved leave confirmation with its official PDF attached."""
    return send_email(
        to_address,
        "Leave Approved – Pointlabs",
        f"Hello {employee_name},\n\nYour {leave_type} leave request for {leave_dates} has been approved. "
        "Please find your official Leave Confirmation attached.",
        "emails/leave_status.html",
        employee_name=employee_name,
        leave_type=leave_type,
        status="approved",
        comment=None,
        preheader="Your official Leave Confirmation is attached.",
        attachments=[(pdf_path, filename, "application/pdf")],
    )
