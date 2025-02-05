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
from sqlalchemy import text
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

def create_app(config_name='development'):
    """Create and configure Flask application with improved error handling"""
    try:
        # Create Flask app
        app = Flask(__name__)
        logger.info(f"Starting application with config: {config_name}")

        # Load configuration
        if config_name not in config:
            logger.warning(f"Invalid config_name: {config_name}, using default")
            config_name = 'default'

        app.config.from_object(config[config_name])

        # Log database URL (without credentials)
        db_url = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if db_url:
            safe_url = db_url.split('@')[-1] if '@' in db_url else db_url
            logger.info(f"Using database: {safe_url}")

        # Initialize extensions
        db.init_app(app)
        migrate = Migrate(app, db)
        login_manager.init_app(app)
        csrf.init_app(app)

        login_manager.login_view = 'auth.login'

        def test_db_connection():
            """Test database connection with enhanced error handling and diagnostics"""
            try:
                with app.app_context():
                    logger.info("Attempting database connection...")
                    
                    # Basic connectivity test
                    db.session.execute(text("SELECT 1")).scalar()
                    logger.info("Basic connectivity test passed")
                    
                    # Simple status check
                    status = db.session.execute(text("""
                        SELECT current_database(), current_timestamp, version()
                    """)).first()
                    
                    if status:
                        logger.info(f"Connected to database: {status[0]}")
                        logger.info(f"Server time: {status[1]}")
                        logger.info(f"Version: {status[2]}")
                    
                    if status:
                        logger.info("Database connection details:")
                        logger.info(f"Database: {status.db_name}")
                        logger.info(f"Server Time: {status.server_time}")
                        logger.info(f"Version: {status.version}")
                        logger.info(f"Active Connections: {status.active_connections}")
                    
                    if status:
                        logger.info("Database connection details:")
                        logger.info(f"Database: {status[0]}")
                        logger.info(f"Timestamp: {status[1]}")
                        logger.info(f"Version: {status[2]}")
                    
                    db.session.commit()
                    return True
                    
                    db.session.commit()
                    return True
                    
            except OperationalError as e:
                logger.error(f"Database operational error: {str(e)}")
                if 'endpoint is disabled' in str(e):
                    logger.error("CRITICAL: Database endpoint is disabled - Please enable it in the Replit Database tool")
                elif 'connection timed out' in str(e):
                    logger.error("Connection timeout - Check network connectivity and firewall settings")
                return False
            except SQLAlchemyError as e:
                logger.error(f"Database SQLAlchemy error: {str(e)}")
                return False
            except Exception as e:
                logger.error(f"Unexpected database error: {str(e)}", exc_info=True)
                return False

        # Attempt database connection with retries
        max_retries = 3
        retry_delay = 5
        connection_successful = False

        for attempt in range(max_retries):
            if test_db_connection():
                connection_successful = True
                break

            if attempt < max_retries - 1:
                logger.info(f"Retrying database connection ({attempt + 1}/{max_retries}) in {retry_delay} seconds...")
                time.sleep(retry_delay)

        if not connection_successful:
            logger.error("All database connection attempts failed")
            raise Exception("Could not establish database connection after multiple attempts")

        # Create tables if they don't exist
        with app.app_context():
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
        port = int(os.environ.get('PORT', 3000))
        logger.info(f"Starting Flask server on port {port}")
        app.run(
            host='0.0.0.0',
            port=port,
            debug=True
        )
    except Exception as e:
        logger.error(f"Error running application: {str(e)}")
        raise