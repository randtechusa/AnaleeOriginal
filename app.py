"""Main application factory with enhanced database management"""
import os
import logging
import time
from flask import Flask, current_app
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import text
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[logging.FileHandler('app.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Initialize Flask extensions
db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()

def validate_database_url():
    """Validate and normalize database URL"""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set")

    # Parse the URL to validate format
    try:
        result = urlparse(database_url)
        if not all([result.scheme, result.hostname, result.username, result.password]):
            raise ValueError("Invalid database URL format")

        # Convert postgres:// to postgresql:// if needed
        if result.scheme == 'postgres':
            database_url = database_url.replace('postgres://', 'postgresql://', 1)

        return database_url
    except Exception as e:
        logger.error(f"Database URL validation failed: {str(e)}")
        raise ValueError(f"Invalid database URL: {str(e)}")

def test_db_connection(db_instance, max_retries=5, retry_delay=3):
    """Test database connection with enhanced retry mechanism"""
    for attempt in range(max_retries):
        try:
            # Ensure we have a fresh connection
            if hasattr(db_instance, 'engine'):
                db_instance.engine.dispose()

            # Test the connection
            db_instance.session.execute(text('SELECT 1'))
            db_instance.session.commit()
            logger.info("Database connection test successful")
            return True

        except (OperationalError, SQLAlchemyError) as e:
            if attempt < max_retries - 1:
                logger.warning(f"Database connection attempt {attempt + 1} failed: {str(e)}")
                time.sleep(retry_delay)
            else:
                logger.error(f"Database connection failed after {max_retries} attempts: {str(e)}")
                raise
    return False

def init_database(app, db_instance):
    """Initialize database with comprehensive error handling"""
    logger.info("Initializing database...")

    try:
        # Validate and configure database URL
        if not app.config.get('SQLALCHEMY_DATABASE_URI'):
            app.config['SQLALCHEMY_DATABASE_URI'] = validate_database_url()

        # Configure SQLAlchemy settings
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_size': 5,
            'max_overflow': 2,
            'pool_timeout': 30,
            'pool_recycle': 1800,
            'pool_pre_ping': True,
            'connect_args': {
                'connect_timeout': 10,
                'application_name': 'iCountant'
            }
        }

        # Initialize database
        db_instance.init_app(app)

        # Test connection with retry mechanism
        with app.app_context():
            db_instance.create_all()
            if test_db_connection(db_instance):
                logger.info("Database initialization completed successfully")
                return True

    except (OperationalError, SQLAlchemyError) as e:
        logger.error(f"Database connection failed: {str(e)}")

        # Configure SQLite fallback
        try:
            logger.info("Attempting SQLite fallback...")
            sqlite_path = os.path.join(app.instance_path, 'dev.db')
            app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{sqlite_path}'
            os.makedirs(app.instance_path, exist_ok=True)

            # Clear existing binds and engine
            if hasattr(db_instance, 'session'):
                db_instance.session.remove()
            if hasattr(db_instance, 'engine'):
                db_instance.engine.dispose()

            with app.app_context():
                db_instance.create_all()
                logger.info("Successfully initialized SQLite fallback database")
                return True

        except Exception as sqlite_error:
            logger.error(f"SQLite fallback failed: {str(sqlite_error)}")
            return False

    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        return False

def create_app(config_name='development'):
    """Create and configure Flask application"""
    app = Flask(__name__)

    try:
        # Load configuration
        if isinstance(config_name, str):
            app.config.from_object(f'config.{config_name.capitalize()}Config')
        else:
            app.config.update(config_name)

        # Set up extensions
        login_manager.init_app(app)
        csrf.init_app(app)

        # Configure login views
        login_manager.login_view = 'auth.login'
        login_manager.login_message = 'Please log in to access this page.'
        login_manager.login_message_category = 'info'

        # Initialize database
        if not init_database(app, db):
            logger.error("Failed to initialize database")
            return None

        # Initialize migrations after database setup
        with app.app_context():
            migrate.init_app(app, db)

            # Register blueprints
            logger.info("Registering blueprints...")
            from main import bp as main_bp
            app.register_blueprint(main_bp)

            from auth import bp as auth_bp
            app.register_blueprint(auth_bp)

            from admin import bp as admin_bp
            app.register_blueprint(admin_bp, url_prefix='/admin')

            from errors import bp as errors_bp
            app.register_blueprint(errors_bp)

            logger.info("Application initialization completed successfully")
            return app

    except Exception as e:
        logger.error(f"Application creation failed: {str(e)}")
        return None

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login"""
    if not current_app:
        return None

    try:
        from models import User
        return User.query.get(int(user_id))
    except Exception as e:
        logger.error(f"Error loading user {user_id}: {str(e)}")
        return None

if __name__ == '__main__':
    app = create_app('development')
    if app:
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port)
    else:
        logger.error("Failed to create application")