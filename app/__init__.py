from flask import Flask, has_request_context, send_from_directory
from flask_login import current_user

from app.config import CONFIGS
from app.extensions import csrf, db, login_manager, migrate


def create_app(config_name="development"):
    app = Flask(__name__)
    app.config.from_object(CONFIGS[config_name])

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login_form"
    csrf.init_app(app)

    from app import models  # noqa: F401

    from app.auth import bp as auth_bp
    from app.auth import routes  # noqa: F401
    from app.main import bp as main_bp
    from app.main import routes  # noqa: F401

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    @app.get("/service-worker.js")
    def service_worker():
        response = send_from_directory(app.static_folder, "service-worker.js", mimetype="application/javascript")
        response.headers["Service-Worker-Allowed"] = "/"
        response.headers["Cache-Control"] = "no-cache"
        return response

    @app.before_request
    def apply_effective_resignations():
        # A runtime safeguard complements scheduled administration: historical data remains,
        # but an employee cannot continue using the platform after their effective exit date.
        from app.services.hr import deactivate_resigned_employees

        deactivate_resigned_employees()

    @app.context_processor
    def workspace_context():
        if not has_request_context() or not current_user.is_authenticated:
            return {"workspace_sticky_notes": []}
        from datetime import datetime
        from app.models.hr import WorkspaceNote
        notes = WorkspaceNote.query.filter(
            ((WorkspaceNote.user_id == current_user.id) & (WorkspaceNote.show_everywhere.is_(True))) |
            (WorkspaceNote.is_global.is_(True)),
            (WorkspaceNote.expires_at.is_(None)) | (WorkspaceNote.expires_at >= datetime.utcnow()),
        ).order_by(WorkspaceNote.created_at.desc()).limit(3).all()
        return {"workspace_sticky_notes": notes}

    @app.cli.command("init-db")
    def init_db():
        db.create_all()

    @app.cli.command("seed-demo")
    def seed_demo():
        from app.services.seed import seed_reference_data
        db.create_all(); seed_reference_data(app.config.get("TEST_ADMIN_PASSWORD", "admin123"))

    @app.cli.command("process-birthdays")
    def process_birthdays():
        from app.services.birthdays import process_birthdays as process
        process()

    @app.cli.command("process-reminders")
    def process_reminders():
        """Send due workspace-task alarms once; schedule this command every few minutes."""
        from app.services.reminders import process_due_task_reminders
        count = process_due_task_reminders()
        print(f"Processed {count} due task reminder(s).")

    @app.cli.command("process-compliance")
    def process_compliance():
        """Create once-only Passport and Emirates ID expiry alerts for scheduled use."""
        from app.services.compliance import process_expiry_reminders
        print(f"Processed {process_expiry_reminders()} credential-expiry reminder(s).")

    @login_manager.user_loader
    def load_user(user_id):
        from app.models.user import User
        return db.session.get(User, int(user_id))
    return app
