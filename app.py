"""Main application configuration and initialization"""
import os
import logging
import sys
import time
from datetime import datetime
from flask import Flask, current_app, redirect, url_for
from flask_migrate import Migrate
from dotenv import load_dotenv
from sqlalchemy import text
from flask_apscheduler import APScheduler
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager

# Configure logging with detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log')
    ]
)

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Flask extensions
db = None  # Will be initialized with app context
migrate = Migrate()
scheduler = APScheduler()
csrf = CSRFProtect()
login_manager = LoginManager()

def verify_database_connection(app):
    """Verify database connection with retries"""
    max_retries = 3
    retry_delay = 5  # seconds

    for attempt in range(max_retries):
        try:
            with app.app_context():
                # Test database connection
                db.session.execute(text('SELECT 1'))
                logger.info("Database connection verified successfully")
                return True
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Database connection attempt {attempt + 1} failed: {str(e)}")
                time.sleep(retry_delay)
            else:
                logger.error(f"Database connection failed after {max_retries} attempts: {str(e)}")
                return False
    return False

def create_app(env=None):
    """Create and configure the Flask application"""
    try:
        logger.info("Starting application creation...")
        global db

        # Initialize Flask application
        app = Flask(__name__,
                   template_folder='templates',
                   static_folder='static')

        # Get database URL with environment separation
        if env == 'production':
            database_url = os.environ.get('DATABASE_URL')
            if not database_url:
                logger.error("Production DATABASE_URL environment variable not set")
                raise ValueError("Production DATABASE_URL not configured")
        else:
            # Use development database if not in production
            database_url = os.environ.get('DEV_DATABASE_URL', os.environ.get('DATABASE_URL'))
            if not database_url:
                logger.error("Development DATABASE_URL environment variable not set")
                raise ValueError("Development DATABASE_URL not configured")

        logger.info("Configuring application...")

        # Configure Flask app with enhanced security
        app.config.update({
            'SECRET_KEY': os.environ.get('FLASK_SECRET_KEY', os.urandom(32)),
            'SQLALCHEMY_DATABASE_URI': database_url,
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
            'TEMPLATES_AUTO_RELOAD': True,
            'WTF_CSRF_ENABLED': True,
            'WTF_CSRF_TIME_LIMIT': 3600,
            'SESSION_COOKIE_SECURE': True,
            'SESSION_COOKIE_HTTPONLY': True,
            'REMEMBER_COOKIE_SECURE': True,
            'REMEMBER_COOKIE_HTTPONLY': True,
            'PROTECT_CORE_FEATURES': True  # Protection flag for core functionalities
        })

        # Import db after app creation to avoid circular imports
        from models import db as models_db, User
        global db
        db = models_db

        # Initialize extensions with app context
        db.init_app(app)
        migrate.init_app(app, db)
        csrf.init_app(app)

        # Configure login manager
        login_manager.init_app(app)
        login_manager.login_view = 'auth.login'
        login_manager.login_message = 'Please log in to access this page.'
        login_manager.login_message_category = 'info'
        login_manager.session_protection = 'strong'

        @login_manager.user_loader
        def load_user(user_id):
            """Load user by ID with enhanced error handling"""
            if not user_id:
                return None
            return User.query.get(int(user_id))

        # Import and register blueprints within app context
        with app.app_context():
            # Verify database connection with retries
            if not verify_database_connection(app):
                logger.error("Failed to establish database connection")
                return None

            # Import blueprints
            from auth import auth
            from routes import main
            from historical_data import historical_data #Added
            from errors import errors #Added

            # Register blueprints with core feature protection
            if app.config['PROTECT_CORE_FEATURES']:
                app.register_blueprint(auth)
                app.register_blueprint(main)
                app.register_blueprint(historical_data) #Added
                app.register_blueprint(errors) #Added

            # Ensure database tables exist
            db.create_all()
            logger.info("Database tables verified")

            return app

    except Exception as e:
        logger.error(f"Critical error in application creation: {str(e)}")
        return None

def main():
    """Main entry point for the application"""
    try:
        # Determine environment
        env = os.environ.get('FLASK_ENV', 'development')
        app = create_app(env)

        if app:
            port = int(os.environ.get('PORT', 5000))
            app.run(host='0.0.0.0', port=port)
        else:
            logger.error("Application creation failed")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()