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

def create_app(config_name='development'):
    """Create and configure Flask application with improved error handling"""
    app = Flask(__name__)

    try:
        logger.info(f"Starting application with config: {config_name}")

        # Basic Configuration
        app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24).hex())
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

        # Get database URL from environment
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            raise ValueError("DATABASE_URL environment variable is not set")

        # Convert postgres:// to postgresql:// if needed
        if db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql://', 1)

        app.config['SQLALCHEMY_DATABASE_URI'] = db_url
        logger.info(f"Using database URL: {db_url.split('@')[1] if db_url else 'No URL'}")

        # Minimal database configuration
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': True,
            'pool_size': 1,
            'max_overflow': 0,
            'pool_timeout': 30,
            'pool_recycle': 1800
        }

        # Initialize extensions
        db.init_app(app)
        migrate = Migrate(app, db)
        login_manager.init_app(app)
        csrf.init_app(app)

        login_manager.login_view = 'auth.login'

        # Test database connection
        with app.app_context():
            try:
                logger.info("Testing database connection...")
                db.session.execute(text('SELECT 1'))
                logger.info("Database connection successful")

                logger.info("Creating database tables...")
                db.create_all()
                logger.info("Database tables created successfully")

            except OperationalError as e:
                logger.error(f"Database connection error: {str(e)}")
                logger.error(f"Original error: {getattr(e, 'orig', 'No original error')}")
                raise

            except Exception as e:
                logger.error(f"Unexpected database error: {str(e)}")
                raise

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
    app = create_app('development')
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=True)