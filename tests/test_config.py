from app import create_app


def test_testing_config_uses_isolated_sqlite():
    app = create_app("testing")

    assert app.config["TESTING"] is True
    assert app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite")


def test_factory_registers_core_blueprints():
    app = create_app("testing")

    assert "auth" in app.blueprints
    assert "main" in app.blueprints
