import os


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "development-only-secret")
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class DevelopmentConfig(BaseConfig):
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///pointlabs-one.db")


class TestingConfig(BaseConfig):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"


CONFIGS = {"development": DevelopmentConfig, "testing": TestingConfig}
