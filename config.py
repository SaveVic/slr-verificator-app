import os

# Get the absolute path of the directory the config.py file is in.
basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration class."""

    # Secret key for session management and CSRF protection
    SECRET_KEY = os.environ.get("SECRET_KEY", "a_very_secure_default_secret_key")

    # Database configuration for SQLite
    # The database file will be stored in the 'instance' folder,
    # which is automatically created by Flask and is not part of the app package.
    # This setup allows using an environment variable for production (e.g., with MySQL)
    # but defaults to a simple SQLite DB for development.
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL"
    ) or "sqlite:///" + os.path.join(basedir, "instance", "app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
