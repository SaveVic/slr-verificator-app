from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config
import os

# Initialize extensions, but don't configure them for a specific app yet
db = SQLAlchemy()
login_manager = LoginManager()
# The 'main.login' string tells Flask-Login which blueprint and view function to redirect to
login_manager.login_view = "main.login"
login_manager.login_message_category = "info"
login_manager.login_message = "Please log in to access this page."


def create_app(config_class=Config):
    """
    Creates and configures an instance of the Flask application.
    This is the Application Factory.
    """
    app = Flask(__name__, instance_relative_config=True)

    # Load configuration from the config object
    app.config.from_object(config_class)

    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Initialize extensions with the app
    db.init_app(app)
    login_manager.init_app(app)

    # Register blueprints
    # A blueprint is a way to organize a group of related views and other code.
    from app.routes import bp as main_bp

    app.register_blueprint(main_bp)

    # Register custom CLI commands
    from app.commands import register_commands

    register_commands(app)

    # Define the user loader function for Flask-Login
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("errors/403.html"), 403

    return app
