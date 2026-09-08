from datetime import datetime, timedelta
import secrets
from flask import redirect, request, render_template, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.auth import bp
from app.models.user import PasswordResetCode, User
from app.extensions import db
from app.services.email import send_password_reset_email

@bp.get("/login")
def login_form():
    return render_template("login.html")


@bp.post("/login")
def login():
    username = request.form.get("username", "").strip()
    user = User.query.filter_by(username=username).first()
    if user is None or not user.is_active or not user.check_password(request.form.get("password", "")):
        return (
            render_template(
                "login.html",
                username=username,
                login_error="Check your user ID and password, then try again.",
            ),
            401,
        )
    login_user(user)
    if user.must_change_password:
        return redirect(url_for("auth.change_password"))
    return redirect(url_for("main.dashboard"))


@bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        if not current_user.check_password(request.form.get("current_password", "")):
            return "Current password is incorrect", 400
        current_user.set_password(request.form["new_password"])
        current_user.must_change_password = False
        from app.extensions import db
        db.session.commit()
        return redirect(url_for("main.dashboard"))
    return render_template("change_password.html")

@bp.get("/logout")
@login_required
def logout():
    logout_user(); return redirect(url_for("auth.login_form"))

@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        user = User.query.filter_by(username=request.form.get("username"), email=request.form.get("email")).first()
        if user:
            code = f"{secrets.randbelow(1000000):06d}"
            db.session.add(PasswordResetCode(user_id=user.id, code=code, expires_at=datetime.utcnow()+timedelta(minutes=15)))
            db.session.commit(); send_password_reset_email(user.email, code)
        return redirect(url_for("auth.reset_password"))
    return render_template("forgot_password.html")

@bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    if request.method == "POST":
        user=User.query.filter_by(username=request.form.get("username")).first()
        record=PasswordResetCode.query.filter_by(user_id=user.id if user else None, code=request.form.get("code"), used_at=None).order_by(PasswordResetCode.id.desc()).first()
        if record and record.expires_at >= datetime.utcnow():
            user.set_password(request.form["new_password"]); user.must_change_password=False; record.used_at=datetime.utcnow(); db.session.commit(); return redirect(url_for("auth.login_form"))
        return "Invalid or expired OTP", 400
    return render_template("reset_password.html")
