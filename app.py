"""Main application factory with enhanced logging and protection"""
import os
import logging
from datetime import datetime
import time
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
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[logging.FileHandler('app.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

login_manager = LoginManager()
csrf = CSRFProtect()

def test_db_connection(app, max_retries=5, retry_delay=3):
    """Test database connection with enhanced retry logic"""
    retry_count = 0
    while retry_count < max_retries:
        try:
            with app.app_context():
                # Test connection with timeout
                with db.engine.connect() as connection:
                    connection.execute("SELECT 1")
                logger.info("Database connection successful")
                return True
        except (OperationalError, SQLAlchemyError) as e:
            retry_count += 1
            logger.warning(f"Database connection attempt {retry_count} failed: {str(e)}")
            if retry_count < max_retries:
                time.sleep(retry_delay)  # Wait before retrying
            else:
                logger.error(f"Database connection failed after {max_retries} attempts")
                return False
    return False

def create_app(config_name='development'):
    """Create and configure Flask application with improved error handling"""
    try:
        app = Flask(__name__)

        # Load configuration
        logger.info(f"Loading configuration for environment: {config_name}")
        app.config.from_object(config[config_name])

        # Initialize extensions
        logger.info("Initializing Flask extensions")
        db.init_app(app)

        # Test database connection before proceeding
        if not test_db_connection(app):
            raise Exception("Could not establish database connection after multiple attempts")

        # Complete initialization after successful database connection
        Migrate(app, db)
        login_manager.init_app(app)
        login_manager.login_view = 'auth.login'
        csrf.init_app(app)

        # Register blueprints
        with app.app_context():
            logger.info("Registering blueprints")
            from auth.routes import auth
            from main.routes import main
            from historical_data import historical_data
            from bank_statements import bank_statements
            from reports import reports
            from chat import chat
            from errors import errors
            from admin import admin

            app.register_blueprint(auth)
            app.register_blueprint(main)
            app.register_blueprint(historical_data)
            app.register_blueprint(bank_statements)
            app.register_blueprint(reports)
            app.register_blueprint(chat)
            app.register_blueprint(admin)
            app.register_blueprint(errors)

            # Initialize database
            try:
                db.create_all()
                logger.info("Database tables created successfully")
            except Exception as e:
                logger.error(f"Error creating database tables: {str(e)}")
                raise

        return app

    except Exception as e:
        logger.error(f"Error creating application: {str(e)}")
        raise

@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except Exception as e:
        logger.error(f"Error loading user {user_id}: {str(e)}")
        return None

def main():
    """Main entry point for the application"""
    try:
        # Create the application instance
        app = create_app('development')

        if app:
            # Run the application
            port = int(os.environ.get('PORT', 5000))
            app.run(
                host='0.0.0.0',
                port=port,
                debug=True
            )
    except Exception as e:
        logger.error(f"Error running application: {str(e)}")
        raise

if __name__ == '__main__':
    main()