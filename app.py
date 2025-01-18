"""Main application factory with enhanced logging and protection"""
import os
import logging
from flask import Flask, render_template
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from models import db, User

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask extensions
login_manager = LoginManager()
csrf = CSRFProtect()

def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__)

    # Database configuration
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")

    # Configure app
    app.config.update(
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY=os.environ.get('SECRET_KEY', os.urandom(32)),
        WTF_CSRF_ENABLED=True,
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True
    )

    # Initialize extensions
    db.init_app(app)
    migrate = Migrate(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    csrf.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return User.query.get(int(user_id))
        except Exception as e:
            logger.error(f"Error loading user {user_id}: {str(e)}")
            return None

    # Register blueprints
    with app.app_context():
        from auth.routes import auth
        from main.routes import main
        from historical_data import historical_data
        from bank_statements import bank_statements
        from reports import reports
        from chat import chat
        from errors import errors

        blueprints = [
            (auth, "Authentication"),
            (main, "Main Application"),
            (historical_data, "Historical Data"),
            (bank_statements, "Bank Statements"),
            (reports, "Reports"),
            (chat, "Chat"),
            (errors, "Error Handling")
        ]

        for blueprint, name in blueprints:
            try:
                app.register_blueprint(blueprint)
                logger.info(f"Registered {name} blueprint")
            except Exception as e:
                logger.error(f"Failed to register {name} blueprint: {str(e)}")
                raise

    # Error handlers
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        logger.error(f"Internal Server Error: {str(error)}")
        return render_template('error.html', error=error), 500

    @app.errorhandler(Exception)
    def handle_exception(error):
        db.session.rollback()
        logger.error(f"Unhandled Exception: {str(error)}", exc_info=True)
        return render_template('error.html', error=error), 500

    return app

if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)