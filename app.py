"""Main application factory with enhanced logging and protection"""
import os
import logging
from datetime import datetime
from flask import Flask, render_template, request
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy import text
from models import db, User

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

login_manager = LoginManager()
csrf = CSRFProtect()

def init_db(app, retries=3):
    """Initialize database with retry mechanism"""
    for attempt in range(retries):
        try:
            logger.info(f"Database initialization attempt {attempt + 1}/{retries}")
            with app.app_context():
                # Test connection
                db.session.execute(text('SELECT 1'))
                db.session.commit()
                logger.info("Database connection successful")

                # Create tables
                db.create_all()
                logger.info("Database tables created successfully")
                return True
        except Exception as e:
            logger.warning(f"Database initialization attempt {attempt + 1} failed: {str(e)}")
            if attempt < retries - 1:  # Don't sleep on the last attempt
                import time
                time.sleep(2 ** attempt)  # Exponential backoff
            db.session.remove()
    return False

def create_app(config_name='development'):
    """Create and configure Flask application with improved error handling"""
    app = Flask(__name__)

    try:
        logger.info(f"Starting application with config: {config_name}")

        # Basic Configuration
        app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24).hex())
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

        # Database Configuration
        if os.environ.get('DATABASE_URL'):
            db_url = os.environ.get('DATABASE_URL')
            if db_url.startswith('postgres://'):
                db_url = db_url.replace('postgres://', 'postgresql://', 1)
            app.config['SQLALCHEMY_DATABASE_URI'] = db_url
            logger.info("Using PostgreSQL database")
        else:
            sqlite_path = os.path.join(app.instance_path, 'dev.db')
            os.makedirs(app.instance_path, exist_ok=True)
            app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{sqlite_path}'
            logger.info("Using SQLite database")

        # Database Engine Configuration
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': True,
            'pool_size': 5,
            'max_overflow': 10,
            'pool_timeout': 30,
            'pool_recycle': 1800,
            'connect_args': {
                'connect_timeout': 10,
                'application_name': 'icountant'
            }
        }

        # Initialize extensions
        db.init_app(app)
        migrate = Migrate(app, db)
        login_manager.init_app(app)
        csrf.init_app(app)

        login_manager.login_view = 'auth.login'

        # Initialize database with retries
        if not init_db(app):
            logger.error("Failed to initialize database after multiple attempts")
            raise Exception("Database initialization failed")

        logger.info("Application initialized successfully")
        return app

    except Exception as e:
        logger.error(f"Application creation failed: {str(e)}")
        logger.exception("Full error traceback:")
        raise

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID with error handling"""
    try:
        return db.session.get(User, int(user_id))
    except Exception as e:
        logger.error(f"Error loading user {user_id}: {str(e)}")
        return None

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=False)