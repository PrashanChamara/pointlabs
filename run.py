import os

from app import create_app

app = create_app(os.environ.get("FLASK_CONFIG", "development"))


def main():
    """Run Pointlabs One locally with ``python run.py``."""
    app.run(
        host="127.0.0.1",
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG", "1") == "1",
    )


if __name__ == "__main__":
    main()
