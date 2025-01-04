"""Main application configuration and initialization"""
import os
import logging
import sys
import time
from datetime import datetime
from flask import Flask, redirect, url_for, flash
from flask_migrate import Migrate
from dotenv import load_dotenv
from sqlalchemy import text
from flask_login import LoginManager
from models import db, User

# Configure logging
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
migrate = Migrate()
login_manager = LoginManager()

def verify_database_connection(app, max_retries=5, retry_delay=3):
    """Verify database connection with retries"""
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

def create_app():
    """Create and configure the Flask application"""
    try:
        logger.info("Starting application creation...")

        # Initialize Flask application
        app = Flask(__name__,
                   template_folder='templates',
                   static_folder='static')

        # Get database URL and ensure it's in the correct format
        db_url = os.environ.get('DATABASE_URL')
        if db_url and db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql://', 1)

        # Basic configuration
        app.config.update({
            'SECRET_KEY': os.environ.get('FLASK_SECRET_KEY', os.urandom(32)),
            'SQLALCHEMY_DATABASE_URI': db_url,
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
            'SQLALCHEMY_ENGINE_OPTIONS': {
                'pool_size': 5,
                'max_overflow': 10,
                'pool_timeout': 30,
                'pool_recycle': 1800,
            }
        })

        # Initialize extensions with app
        db.init_app(app)
        migrate.init_app(app, db)

        # Configure login manager
        login_manager.init_app(app)
        login_manager.login_view = 'auth.login'
        login_manager.login_message = 'Please log in to access this page.'
        login_manager.login_message_category = 'info'

        @login_manager.user_loader
        def load_user(user_id):
            """Load user by ID"""
            try:
                return User.query.get(int(user_id))
            except Exception as e:
                logger.error(f"Error loading user {user_id}: {str(e)}")
                return None

        # Register blueprints and initialize database
        with app.app_context():
            # Import and register blueprints
            from auth.routes import auth
            app.register_blueprint(auth)

            # Verify database connection
            if not verify_database_connection(app):
                raise Exception("Failed to establish database connection")

            # Create database tables
            db.create_all()
            logger.info("Database tables created successfully")

            # Create admin user if not exists
            from auth.routes import create_admin_if_not_exists
            create_admin_if_not_exists()

            logger.info("Application created successfully")
            return app

    except Exception as e:
        logger.error(f"Error in application creation: {str(e)}")
        return None

if __name__ == '__main__':
    app = create_app()
    if app:
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port)
    else:
        logger.error("Application creation failed")
        sys.exit(1)