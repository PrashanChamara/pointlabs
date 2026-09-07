from flask import Flask

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

    @app.cli.command("init-db")
    def init_db():
        db.create_all()

    @app.cli.command("seed-demo")
    def seed_demo():
        from app.services.seed import seed_reference_data
        db.create_all(); seed_reference_data(app.config.get("TEST_ADMIN_PASSWORD", "admin123"))

    @login_manager.user_loader
    def load_user(user_id):
        from app.models.user import User
        return db.session.get(User, int(user_id))
    return app
