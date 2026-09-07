import os


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "development-only-secret")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TEST_ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD", "admin123")


class DevelopmentConfig(BaseConfig):
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///pointlabs-one.db")
    WTF_CSRF_ENABLED = False


class TestingConfig(BaseConfig):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"


CONFIGS = {"development": DevelopmentConfig, "testing": TestingConfig}
