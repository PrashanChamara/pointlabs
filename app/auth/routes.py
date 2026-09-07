from flask import redirect, request, render_template, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.auth import bp
from app.models.user import User

@bp.get("/login")
def login_form():
    return render_template("login.html")


@bp.post("/login")
def login():
    user = User.query.filter_by(username=request.form.get("username", "")).first()
    if user is None or not user.check_password(request.form.get("password", "")):
        return "Invalid credentials", 401
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
