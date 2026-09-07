from datetime import date, datetime, timedelta
from pathlib import Path
from flask import current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from app.extensions import db
from app.main import bp
from app.models.hr import BirthdayVoucher, EmployeeDocument, LeaveBalance, LeaveRequest, LeaveType, Notification
from app.models.organization import Designation
from app.models.user import EmployeeProfile, User

@bp.get("/")
@login_required
def dashboard():
    pending = LeaveRequest.query.filter_by(status="submitted").count() if current_user.is_administrator else 0
    today = LeaveRequest.query.filter(LeaveRequest.status == "approved", LeaveRequest.start_date <= date.today(), LeaveRequest.end_date >= date.today()).all()
    return render_template("dashboard.html", pending=pending, today=today, notifications=Notification.query.filter_by(user_id=current_user.id, is_read=False).all())

@bp.route("/leave", methods=["GET", "POST"])
@login_required
def leave():
    if request.method == "POST":
        start, end = date.fromisoformat(request.form["start_date"]), date.fromisoformat(request.form["end_date"])
        item = LeaveRequest(user_id=current_user.id, leave_type_id=int(request.form["leave_type"]), start_date=start, end_date=end, days=(end-start).days+1, reason=request.form.get("reason"))
        db.session.add(item); db.session.commit(); flash("Leave request submitted."); return redirect(url_for("main.leave"))
    return render_template("leave.html", requests=LeaveRequest.query.filter_by(user_id=current_user.id).all(), leave_types=LeaveType.query.filter_by(is_active=True).all())

@bp.post("/leave/<int:request_id>/<action>")
@login_required
def review_leave(request_id, action):
    item = db.get_or_404(LeaveRequest, request_id)
    if not (current_user.is_administrator or (item.user.employee_profile and item.user.employee_profile.reporting_officer_id == current_user.id)): return "Forbidden", 403
    item.status = {"approve":"approved", "reject":"rejected", "return":"returned"}.get(action, item.status); item.reviewer_comment=request.form.get("comment")
    if item.status == "approved":
        balance=LeaveBalance.query.filter_by(user_id=item.user_id, leave_type_id=item.leave_type_id).first()
        if balance: balance.available_days -= item.days
    db.session.add(Notification(user_id=item.user_id, message=f"Your leave request was {item.status}.")); db.session.commit(); return redirect(url_for("main.dashboard"))

@bp.route("/admin/employees", methods=["GET", "POST"])
@login_required
def employees():
    if not current_user.is_administrator: return "Forbidden", 403
    if request.method == "POST":
        user=User(username=request.form["username"], email=request.form.get("email"), must_change_password=True); user.set_password(request.form.get("password", "ChangeMe123!")); db.session.add(user); db.session.flush(); db.session.add(EmployeeProfile(user_id=user.id, employee_code=request.form.get("employee_code"), full_name=request.form["full_name"])); db.session.commit(); flash("Employee created."); return redirect(url_for("main.employees"))
    return render_template("employees.html", employees=EmployeeProfile.query.order_by(EmployeeProfile.full_name).all())

@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    profile = current_user.employee_profile
    if profile is None: return "No employee profile yet", 404
    if request.method == "POST":
        profile.phone=request.form.get("phone"); profile.address=request.form.get("address"); db.session.commit(); flash("Profile updated."); return redirect(url_for("main.profile"))
    return render_template("profile.html", profile=profile)

@bp.route("/admin/designations", methods=["GET", "POST"])
@login_required
def designations():
    if not current_user.is_administrator: return "Forbidden", 403
    if request.method == "POST":
        name=request.form["name"].strip()
        if name and not Designation.query.filter_by(name=name).first():
            db.session.add(
                Designation(
                    name=name,
                    is_reporting_officer_designation=bool(request.form.get("reporting")),
                )
            )
            db.session.commit()
        return redirect(url_for("main.designations"))
    return render_template("designations.html", designations=Designation.query.order_by(Designation.name).all())

@bp.post("/admin/designations/<int:designation_id>/toggle")
@login_required
def toggle_designation(designation_id):
    if not current_user.is_administrator: return "Forbidden", 403
    item=db.get_or_404(Designation, designation_id); item.is_reporting_officer_designation=not item.is_reporting_officer_designation; db.session.commit(); return redirect(url_for("main.designations"))

@bp.route("/documents", methods=["GET", "POST"])
@login_required
def documents():
    if request.method == "POST":
        file=request.files.get("file")
        if not file or not file.filename: return "File required", 400
        suffix=Path(file.filename).suffix.lower()
        if suffix not in {".pdf", ".png", ".jpg", ".jpeg", ".webp"}: return "Only images and PDFs are allowed", 400
        folder=Path(current_app.instance_path)/"uploads"; folder.mkdir(parents=True, exist_ok=True)
        safe=f"{current_user.id}_{int(datetime.utcnow().timestamp())}{suffix}"; file.save(folder/safe)
        db.session.add(EmployeeDocument(user_id=current_user.id, category=request.form.get("category", "Other"), filename=file.filename, stored_path=safe)); db.session.commit(); flash("Document uploaded."); return redirect(url_for("main.documents"))
    return render_template("documents.html", documents=EmployeeDocument.query.filter_by(user_id=current_user.id).all())

@bp.get("/reports/leave.csv")
@login_required
def leave_report():
    if not (current_user.is_administrator or current_user.employee_profile): return "Forbidden",403
    from io import BytesIO
    import csv
    output=BytesIO(); text=output.write
    rows=["Employee,Leave type,Start,End,Days,Status\n"]+[f'"{r.user.employee_profile.full_name if r.user.employee_profile else r.user.username}","{r.leave_type.name}",{r.start_date},{r.end_date},{r.days},{r.status}\n' for r in LeaveRequest.query.order_by(LeaveRequest.created_at.desc()).all()]
    output.write("".join(rows).encode()); output.seek(0); return send_file(output, mimetype="text/csv", as_attachment=True, download_name="leave-report.csv")

@bp.get("/birthdays")
@login_required
def birthdays():
    if not current_user.is_administrator: return "Forbidden", 403
    until=date.today()+timedelta(days=3); people=[p for p in EmployeeProfile.query.all() if p.date_of_birth and (p.date_of_birth.replace(year=date.today().year) >= date.today()) and p.date_of_birth.replace(year=date.today().year) <= until]
    return render_template("birthdays.html", people=people)
