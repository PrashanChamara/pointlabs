from datetime import date, datetime, timedelta
from io import BytesIO, StringIO
from pathlib import Path
import csv

from flask import current_app, flash, redirect, render_template, request, send_file, send_from_directory, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from app.extensions import db
from app.main import bp
from app.models.hr import DirectMessage, EmployeeDocument, LeaveBalance, LeaveRequest, LeaveType, Notification
from app.models.organization import Department, Designation, Location
from app.models.user import EmployeeProfile, User
from app.services.email import send_email


def admin_only():
    return None if current_user.is_administrator else ("Forbidden", 403)


def greeting_for_hour(hour):
    if 5 <= hour < 12:
        return "Good morning"
    if 12 <= hour < 18:
        return "Good afternoon"
    return "Good evening"


def display_name(user):
    return user.employee_profile.full_name if user.employee_profile else user.username


def ensure_profile(user):
    """Repair historic test users created before profiles became mandatory."""
    if user.employee_profile is None:
        db.session.add(EmployeeProfile(
            user_id=user.id,
            employee_code="PL-ADMIN-001" if user.is_administrator else None,
            full_name="Pointlabs Administrator" if user.is_administrator else user.username,
        ))
        db.session.commit()
    return user.employee_profile


@bp.get("/")
@login_required
def dashboard():
    pending = LeaveRequest.query.filter_by(status="submitted").count() if current_user.is_administrator else 0
    today = LeaveRequest.query.filter(LeaveRequest.status == "approved", LeaveRequest.start_date <= date.today(), LeaveRequest.end_date >= date.today()).all()
    notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).order_by(Notification.created_at.desc()).all()
    return render_template(
        "dashboard.html", pending=pending, today=today, notifications=notifications,
        unread_messages=DirectMessage.query.filter_by(recipient_id=current_user.id, is_read=False).count(),
        greeting=greeting_for_hour(datetime.now().hour), people_count=EmployeeProfile.query.count(),
    )


@bp.route("/leave", methods=["GET", "POST"])
@login_required
def leave():
    if request.method == "POST":
        start, end = date.fromisoformat(request.form["start_date"]), date.fromisoformat(request.form["end_date"])
        if end < start:
            flash("End date must be on or after the start date.")
            return redirect(url_for("main.leave"))
        db.session.add(LeaveRequest(user_id=current_user.id, leave_type_id=int(request.form["leave_type"]), start_date=start, end_date=end, days=(end - start).days + 1, reason=request.form.get("reason", "").strip() or None))
        db.session.commit()
        flash("Leave request submitted for review.")
        return redirect(url_for("main.leave"))
    return render_template("leave.html", requests=LeaveRequest.query.filter_by(user_id=current_user.id).order_by(LeaveRequest.created_at.desc()).all(), leave_types=LeaveType.query.filter_by(is_active=True).all())


@bp.post("/leave/<int:request_id>/<action>")
@login_required
def review_leave(request_id, action):
    item = db.get_or_404(LeaveRequest, request_id)
    permitted = current_user.is_administrator or (item.user.employee_profile and item.user.employee_profile.reporting_officer_id == current_user.id)
    if not permitted:
        return "Forbidden", 403
    result = {"approve": "approved", "reject": "rejected", "return": "returned"}.get(action)
    if result is None:
        return "Unknown action", 400
    item.status, item.reviewer_comment = result, request.form.get("comment", "").strip() or None
    if result == "approved":
        balance = LeaveBalance.query.filter_by(user_id=item.user_id, leave_type_id=item.leave_type_id).first()
        if balance:
            balance.available_days -= item.days
    message = f"{display_name(item.user)}'s {item.leave_type.name} leave request was {result}."
    db.session.add(Notification(user_id=item.user_id, message=message))
    db.session.commit()
    for address in {current_app.config.get("SMTP_FROM"), item.user.email} - {None, ""}:
        send_email(address, f"Pointlabs One · Leave {result}", f"{message}\n{item.reviewer_comment or ''}")
    flash(f"Leave request {result}.")
    return redirect(url_for("main.dashboard"))


@bp.route("/admin/employees", methods=["GET", "POST"])
@login_required
def employees():
    denied = admin_only()
    if denied:
        return denied
    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form.get("email", "").strip() or None
        if User.query.filter_by(username=username).first() or (email and User.query.filter_by(email=email).first()):
            flash("The user ID or email address is already in use.")
            return redirect(url_for("main.employees"))
        user = User(username=username, email=email, must_change_password=True)
        user.set_password(request.form.get("password") or "ChangeMe123!")
        db.session.add(user)
        db.session.flush()
        db.session.add(EmployeeProfile(user_id=user.id, employee_code=request.form.get("employee_code", "").strip() or None, full_name=request.form["full_name"].strip(), department_id=request.form.get("department_id", type=int), designation_id=request.form.get("designation_id", type=int), location_id=request.form.get("location_id", type=int)))
        db.session.commit()
        flash("Employee account created. They will change the temporary password on first sign-in.")
        return redirect(url_for("main.employees"))
    q = request.args.get("q", "").strip()
    designation_id, department_id = request.args.get("designation_id", type=int), request.args.get("department_id", type=int)
    query = EmployeeProfile.query.join(User, EmployeeProfile.user_id == User.id).order_by(EmployeeProfile.full_name)
    if q:
        query = query.filter(or_(EmployeeProfile.full_name.ilike(f"%{q}%"), EmployeeProfile.employee_code.ilike(f"%{q}%"), User.email.ilike(f"%{q}%")))
    if designation_id:
        query = query.filter(EmployeeProfile.designation_id == designation_id)
    if department_id:
        query = query.filter(EmployeeProfile.department_id == department_id)
    return render_template("employees.html", employees=query.all(), designations=Designation.query.order_by(Designation.name).all(), departments=Department.query.order_by(Department.name).all(), locations=Location.query.order_by(Location.name).all())


@bp.get("/admin/employees/export.csv")
@login_required
def employee_export():
    denied = admin_only()
    if denied:
        return denied
    stream = StringIO(); writer = csv.writer(stream)
    writer.writerow(["Employee ID", "Name", "Email", "Designation", "Department", "Location", "Status"])
    for profile in EmployeeProfile.query.order_by(EmployeeProfile.full_name).all():
        writer.writerow([profile.employee_code or "", profile.full_name, profile.user.email or "", profile.designation.name if profile.designation else "", profile.department.name if profile.department else "", profile.location.name if profile.location else "", "Active" if profile.user.is_active else "Inactive"])
    return send_file(BytesIO(stream.getvalue().encode()), mimetype="text/csv", as_attachment=True, download_name="pointlabs-employees.csv")


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    profile = ensure_profile(current_user)
    if request.method == "POST":
        profile.phone, profile.address = request.form.get("phone", "").strip() or None, request.form.get("address", "").strip() or None
        current_user.email = request.form.get("email", "").strip() or None
        db.session.commit()
        flash("Your profile has been updated.")
        return redirect(url_for("main.profile"))
    return render_template("profile.html", profile=profile)


@bp.route("/documents", methods=["GET", "POST"])
@login_required
def documents():
    if request.method == "POST":
        owner_id = request.form.get("employee_user_id", type=int) if current_user.is_administrator else current_user.id
        owner = db.session.get(User, owner_id) if owner_id else None
        if owner is None or (not current_user.is_administrator and owner.id != current_user.id):
            return "Employee selection is invalid", 400
        file = request.files.get("file")
        if not file or not file.filename:
            flash("Choose a document to upload.")
            return redirect(url_for("main.documents"))
        suffix = Path(file.filename).suffix.lower()
        if suffix not in {".pdf", ".png", ".jpg", ".jpeg", ".webp"}:
            flash("Only PDF and image documents are allowed.")
            return redirect(url_for("main.documents"))
        folder = Path(current_app.instance_path) / "uploads"; folder.mkdir(parents=True, exist_ok=True)
        safe = f"{owner.id}_{int(datetime.now().timestamp())}{suffix}"
        if suffix != ".pdf":
            from PIL import Image
            safe = Path(safe).with_suffix(".webp").name
            image = Image.open(file.stream).convert("RGB"); image.thumbnail((2000, 2000)); image.save(folder / safe, "WEBP", quality=82, method=6)
        else:
            file.save(folder / safe)
        db.session.add(EmployeeDocument(user_id=owner.id, category=request.form.get("category", "Other").strip() or "Other", filename=file.filename, stored_path=safe))
        db.session.commit()
        flash(f"Document uploaded to {display_name(owner)}’s profile.")
        return redirect(url_for("main.documents"))
    docs = EmployeeDocument.query.order_by(EmployeeDocument.uploaded_at.desc()) if current_user.is_administrator else EmployeeDocument.query.filter_by(user_id=current_user.id).order_by(EmployeeDocument.uploaded_at.desc())
    return render_template("documents.html", documents=docs.all(), employees=EmployeeProfile.query.order_by(EmployeeProfile.full_name).all() if current_user.is_administrator else [])


@bp.get("/documents/<int:document_id>/download")
@login_required
def download_document(document_id):
    document = db.get_or_404(EmployeeDocument, document_id)
    if not (current_user.is_administrator or document.user_id == current_user.id):
        return "Forbidden", 403
    return send_from_directory(Path(current_app.instance_path) / "uploads", document.stored_path, as_attachment=True, download_name=document.filename)


@bp.route("/messages", methods=["GET", "POST"])
@login_required
def messages():
    peers = User.query.filter(User.id != current_user.id, User.is_active.is_(True)).order_by(User.username).all()
    selected_id = request.values.get("recipient_id", type=int)
    selected = db.session.get(User, selected_id) if selected_id else (peers[0] if peers else None)
    if selected and selected.id == current_user.id:
        selected = None
    if request.method == "POST":
        body = request.form.get("body", "").strip()
        if selected is None or not body:
            flash("Select a colleague and write a message.")
            return redirect(url_for("main.messages"))
        db.session.add(DirectMessage(sender_id=current_user.id, recipient_id=selected.id, body=body))
        db.session.add(Notification(user_id=selected.id, message=f"New message from {display_name(current_user)}."))
        db.session.commit()
        if selected.email:
            send_email(selected.email, "Pointlabs One · New message", f"{display_name(current_user)} sent you a message in Pointlabs One.\n\n{body}")
        return redirect(url_for("main.messages", recipient_id=selected.id))
    thread = []
    if selected:
        thread = DirectMessage.query.filter(or_((DirectMessage.sender_id == current_user.id) & (DirectMessage.recipient_id == selected.id), (DirectMessage.sender_id == selected.id) & (DirectMessage.recipient_id == current_user.id))).order_by(DirectMessage.created_at).all()
        for item in thread:
            if item.recipient_id == current_user.id:
                item.is_read = True
        db.session.commit()
    return render_template("messages.html", peers=peers, selected=selected, thread=thread)


@bp.get("/reports")
@login_required
def reports():
    denied = admin_only()
    if denied:
        return denied
    leaves = LeaveRequest.query.order_by(LeaveRequest.created_at.desc()).all()
    return render_template("reports.html", employees=EmployeeProfile.query.count(), pending=LeaveRequest.query.filter_by(status="submitted").count(), approved=LeaveRequest.query.filter_by(status="approved").count(), leaves=leaves[:8])


@bp.get("/reports/leave.csv")
@login_required
def leave_report():
    if not (current_user.is_administrator or current_user.employee_profile):
        return "Forbidden", 403
    stream = StringIO(); writer = csv.writer(stream); writer.writerow(["Employee", "Leave type", "Start", "End", "Days", "Status"])
    for item in LeaveRequest.query.order_by(LeaveRequest.created_at.desc()).all():
        writer.writerow([display_name(item.user), item.leave_type.name, item.start_date, item.end_date, item.days, item.status])
    return send_file(BytesIO(stream.getvalue().encode()), mimetype="text/csv", as_attachment=True, download_name="pointlabs-leave-report.csv")


@bp.get("/admin")
@login_required
def admin_panel():
    denied = admin_only()
    if denied:
        return denied
    return render_template("admin_panel.html", people_count=EmployeeProfile.query.count(), documents_count=EmployeeDocument.query.count(), pending_count=LeaveRequest.query.filter_by(status="submitted").count())


@bp.route("/admin/designations", methods=["GET", "POST"])
@login_required
def designations():
    denied = admin_only()
    if denied:
        return denied
    if request.method == "POST":
        name = request.form["name"].strip()
        if name and not Designation.query.filter_by(name=name).first():
            db.session.add(Designation(name=name, is_reporting_officer_designation=bool(request.form.get("reporting")))); db.session.commit()
        return redirect(url_for("main.designations"))
    return render_template("designations.html", designations=Designation.query.order_by(Designation.name).all())


@bp.post("/admin/designations/<int:designation_id>/toggle")
@login_required
def toggle_designation(designation_id):
    denied = admin_only()
    if denied:
        return denied
    item = db.get_or_404(Designation, designation_id); item.is_reporting_officer_designation = not item.is_reporting_officer_designation; db.session.commit()
    return redirect(url_for("main.designations"))


@bp.get("/birthdays")
@login_required
def birthdays():
    denied = admin_only()
    if denied:
        return denied
    until = date.today() + timedelta(days=3)
    people = [profile for profile in EmployeeProfile.query.all() if profile.date_of_birth and date.today() <= profile.date_of_birth.replace(year=date.today().year) <= until]
    return render_template("birthdays.html", people=people)
