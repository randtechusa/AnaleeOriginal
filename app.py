"""Main application configuration and initialization"""
import os
import logging
import sys
from datetime import datetime
from flask import Flask, current_app
from flask_migrate import Migrate 
from dotenv import load_dotenv
from sqlalchemy import text
from flask_apscheduler import APScheduler
from flask_wtf.csrf import CSRFProtect
from models import db, login_manager, User

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log')
    ]
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Load environment variables
load_dotenv()

# Initialize Flask extensions
migrate = Migrate()
scheduler = APScheduler()
csrf = CSRFProtect()

def create_app(env=os.environ.get('FLASK_ENV', 'production')):
    """Create and configure the Flask application"""
    try:
        logger.info("Starting application creation...")

        # Initialize Flask application
        app = Flask(__name__, template_folder='templates', static_folder='static')

        # Get database URL and verify it exists
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            logger.error("DATABASE_URL environment variable not set")
            return None

        logger.info("Database URL found, configuring application...")

        # Configure Flask app with enhanced security
        config = {
            'SECRET_KEY': os.environ.get("FLASK_SECRET_KEY", os.urandom(32)),
            'SQLALCHEMY_DATABASE_URI': database_url,
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
            'TEMPLATES_AUTO_RELOAD': True,
            'WTF_CSRF_ENABLED': True,
            'WTF_CSRF_TIME_LIMIT': 3600,  # 1 hour CSRF token validity
            'SESSION_COOKIE_SECURE': True,
            'SESSION_COOKIE_HTTPONLY': True,
            'REMEMBER_COOKIE_SECURE': True,
            'REMEMBER_COOKIE_HTTPONLY': True,
            'SQLALCHEMY_ENGINE_OPTIONS': {
                'pool_pre_ping': True,
                'pool_size': 5,
                'pool_timeout': 30,
                'pool_recycle': 300,
                'max_overflow': 2
            }
        }

        app.config.update(config)
        logger.info("Application configuration completed")

        # Initialize Flask extensions
        logger.info("Initializing database...")
        db.init_app(app)

        logger.info("Initializing migrations...")
        migrate.init_app(app, db)

        # Initialize CSRF protection
        logger.info("Initializing CSRF protection...")
        csrf.init_app(app)

        # Configure login manager with enhanced security
        logger.info("Configuring login manager...")
        login_manager.init_app(app)
        login_manager.login_view = 'auth.login'
        login_manager.login_message = 'Please log in to access this page.'
        login_manager.login_message_category = 'info'
        login_manager.session_protection = 'strong'

        with app.app_context():
            try:
                # Verify database connection
                logger.info("Verifying database connection...")
                db.session.execute(text("SELECT 1"))
                logger.info("Database connection verified successfully")

                # Register blueprints in specific order
                logger.info("Registering blueprints...")

                # Register auth blueprint first for login functionality
                from auth import auth as auth_blueprint
                app.register_blueprint(auth_blueprint)
                logger.info("Auth blueprint registered")

                # Register admin blueprint with proper prefix
                from admin import admin as admin_blueprint
                app.register_blueprint(admin_blueprint, url_prefix='/admin')
                logger.info("Admin blueprint registered")

                # Register historical data blueprint
                from historical_data import historical_data as historical_data_blueprint
                app.register_blueprint(historical_data_blueprint)
                logger.info("Historical data blueprint registered")

                # Register suggestions blueprint
                from suggestions import suggestions as suggestions_blueprint
                app.register_blueprint(suggestions_blueprint)
                logger.info("Suggestions blueprint registered")

                # Register other blueprints
                from routes import main as main_blueprint
                app.register_blueprint(main_blueprint)
                logger.info("Main blueprint registered")

                # Register report blueprint
                from reports import reports as reports_blueprint
                app.register_blueprint(reports_blueprint, url_prefix='/reports')
                logger.info("Reports blueprint registered")

                # Register bank statements blueprint
                from bank_statements import bank_statements as bank_statements_blueprint
                app.register_blueprint(bank_statements_blueprint)
                logger.info("Bank statements blueprint registered")

                # Ensure database tables exist
                db.create_all()
                logger.info("Database tables verified")

                return app

            except Exception as e:
                logger.error(f"Error during application setup: {str(e)}")
                logger.exception("Full stack trace:")
                return None

    except Exception as e:
        logger.error(f"Critical error in application creation: {str(e)}")
        logger.exception("Full stack trace:")
        return None

if __name__ == '__main__':
    app = create_app()
    if app:
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port)
    else:
        logger.error("Application creation failed")
        sys.exit(1)