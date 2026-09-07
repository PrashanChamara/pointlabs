import os
from pathlib import Path


def load_local_environment():
    """Load ignored development secrets without adding a runtime dependency."""
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if not env_file.is_file():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_local_environment()


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "development-only-secret")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TEST_ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD", "admin123")
    SMTP_HOST = os.environ.get("SMTP_HOST")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
    SMTP_FROM = os.environ.get("SMTP_FROM")


class DevelopmentConfig(BaseConfig):
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///pointlabs-one.db")
    WTF_CSRF_ENABLED = False


class TestingConfig(BaseConfig):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"


CONFIGS = {"development": DevelopmentConfig, "testing": TestingConfig}
