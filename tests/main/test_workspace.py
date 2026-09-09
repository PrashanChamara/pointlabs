from flask import g, has_app_context

from app.extensions import db
from app.models.hr import WorkspaceNote, WorkspaceTask
from app.models.user import EmployeeProfile, User
from app.services.seed import seed_reference_data


def sign_in(client, user):
    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)
        session["_fresh"] = True
    if has_app_context():
        g.pop("_login_user", None)


def test_workspace_tasks_are_private_and_notes_can_be_shared_by_hr(client, app):
    with app.app_context():
        seed_reference_data("admin123")
        admin = User.query.filter_by(username="admin").one()
        employee = User(username="workspace-user", must_change_password=False)
        employee.set_password("password")
        db.session.add(employee); db.session.flush()
        db.session.add(EmployeeProfile(user_id=employee.id, full_name="Workspace User"))
        db.session.commit()
        employee_id = employee.id
        sign_in(client, employee)
    assert client.post("/workspace", data={"action": "task-create", "title": "Prepare handover"}).status_code == 302
    with app.app_context():
        task = WorkspaceTask.query.one()
        assert task.user_id == employee_id
        admin = User.query.filter_by(username="admin").one()
    sign_in(client, admin)
    assert client.post("/workspace", data={"action": "note-create", "body": "Payroll closes Friday", "is_global": "on"}).status_code == 302
    with app.app_context():
        assert WorkspaceNote.query.one().is_global is True
        employee = db.session.get(User, employee_id)
    sign_in(client, employee)
    response = client.get("/workspace")
    assert response.status_code == 200
    assert b"Payroll closes Friday" in response.data
    assert client.post("/workspace", data={"action": "task-delete", "task_id": task.id}).status_code == 302
    with app.app_context():
        assert WorkspaceTask.query.count() == 0
