"""Main application factory with enhanced logging and protection"""
import os
import logging
import time
from datetime import datetime
from flask import Flask, render_template, request
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from models import db, User
from config import config

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

def validate_database_url():
    """Validate database URL format and accessibility"""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set")

    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    logger.info("Database URL validated successfully")
    return database_url

def create_app(config_name='development'):
    """Create and configure Flask application"""
    try:
        # Create Flask app
        app = Flask(__name__)

        # Validate config name
        if config_name not in config:
            logger.warning(f"Invalid config_name: {config_name}, using default")
            config_name = 'default'

        # Load configuration
        app.config.from_object(config[config_name])

        # Validate and update database URL
        try:
            database_url = validate_database_url()
            app.config['SQLALCHEMY_DATABASE_URI'] = database_url
        except Exception as e:
            logger.error(f"Database URL validation failed: {str(e)}")
            raise

        # Initialize extensions
        db.init_app(app)
        migrate = Migrate(app, db)
        login_manager.init_app(app)
        csrf.init_app(app)

        login_manager.login_view = 'auth.login'

        def test_db_connection():
            """Test database connection with enhanced error handling"""
            try:
                with app.app_context():
                    # Test connection
                    connection = db.engine.connect()
                    connection.close()
                    logger.info("Database connection test successful")
                return True
            except OperationalError as e:
                logger.error(f"Database operational error: {str(e)}")
                return False
            except SQLAlchemyError as e:
                logger.error(f"Database SQLAlchemy error: {str(e)}")
                return False
            except Exception as e:
                logger.error(f"Unexpected database error: {str(e)}")
                return False

        # Attempt database connection with retries
        max_retries = 5
        retry_delay = 2

        for attempt in range(max_retries):
            if test_db_connection():
                break

            if attempt < max_retries - 1:
                logger.info(f"Retrying database connection ({attempt + 1}/{max_retries}) in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logger.error("All database connection attempts failed")
                raise Exception("Could not establish database connection after multiple attempts")

        # Register blueprints
        with app.app_context():
            from auth.routes import auth
            from main.routes import main
            from historical_data import historical_data
            from bank_statements import bank_statements
            from reports import reports
            from chat import chat
            from errors import errors
            from admin import admin

            blueprints = [
                auth, main, historical_data, bank_statements,
                reports, chat, admin, errors
            ]

            for blueprint in blueprints:
                app.register_blueprint(blueprint)
                logger.info(f"Registered blueprint: {blueprint.name}")

            try:
                db.create_all()
                logger.info("Database tables created successfully")
            except Exception as e:
                logger.error(f"Error creating database tables: {str(e)}")
                raise

        logger.info("Application created successfully")
        return app

    except Exception as e:
        logger.error(f"Application creation failed: {str(e)}")
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
    try:
        app = create_app('development')
        port = int(os.environ.get('PORT', 8080))
        app.run(
            host='0.0.0.0',
            port=port,
            debug=True
        )
    except Exception as e:
        logger.error(f"Error running application: {str(e)}")
        raise