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

def create_app(config_name='development'):
    """Create and configure Flask application"""
    try:
        app = Flask(__name__)
        app.config.from_object(config[config_name])

        db.init_app(app)
        migrate = Migrate(app, db)  # Initialize Flask-Migrate

        # Test database connection with retry logic
        max_retries = 3
        retry_delay = 2  # seconds

        with app.app_context():
            for attempt in range(max_retries):
                try:
                    db.engine.connect()
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    time.sleep(retry_delay)
                    if "endpoint is disabled" in str(e):
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            continue
                        else:
                            logger.error(f"Database connection failed: {str(e)}")
                            raise
                    else:
                        logger.error(f"Database connection failed: {str(e)}")
                        raise


        login_manager.init_app(app)
        login_manager.login_view = 'auth.login'
        csrf.init_app(app)

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

            try:
                db.create_all()
            except Exception as e:
                logger.error(f"Error creating database tables: {str(e)}")

        return app

    except Exception as e:
        logger.error(f"Application creation failed: {str(e)}")
        raise

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login"""
    try:
        return db.session.get(User, int(user_id))
    except Exception as e:
        logger.error(f"Error loading user {user_id}: {str(e)}")
        return None

def main():
    """Main entry point for the application"""
    try:
        app = create_app('development')
        if app:
            port = int(os.environ.get('PORT', 8080))
            app.run(
                host='0.0.0.0',
                port=port,
                debug=False,
                threaded=True
            )
    except Exception as e:
        logger.error(f"Error running application: {str(e)}")
        raise

if __name__ == '__main__':
    main()