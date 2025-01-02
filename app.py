"""Main application configuration and initialization"""
import os
import logging
import sys
from datetime import datetime
from flask import Flask, current_app, redirect, url_for
from flask_migrate import Migrate
from dotenv import load_dotenv
from sqlalchemy import text
from flask_apscheduler import APScheduler
from flask_wtf.csrf import CSRFProtect
from models import db, login_manager

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
migrate = Migrate()
scheduler = APScheduler()
csrf = CSRFProtect()

def create_app(env=None):
    """Create and configure the Flask application"""
    try:
        logger.info("Starting application creation...")

        # Initialize Flask application
        app = Flask(__name__,
                   template_folder='templates',
                   static_folder='static')

        # Get database URL
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            logger.error("DATABASE_URL environment variable not set")
            raise ValueError("DATABASE_URL not configured")

        logger.info("Configuring application...")

        # Configure Flask app
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
            'SQLALCHEMY_ENGINE_OPTIONS': {
                'pool_pre_ping': True,
                'pool_size': 5,
                'pool_timeout': 30,
                'pool_recycle': 300,
                'max_overflow': 2
            }
        })

        # Initialize extensions
        db.init_app(app)
        migrate.init_app(app, db)
        csrf.init_app(app)

        # Configure login manager
        login_manager.init_app(app)
        login_manager.login_view = 'auth.login'
        login_manager.login_message = 'Please log in to access this page.'
        login_manager.login_message_category = 'info'
        login_manager.session_protection = 'strong'

        with app.app_context():
            try:
                # Verify database connection
                db.session.execute(text('SELECT 1'))
                logger.info("Database connection verified")

                # Import blueprints
                from auth import auth
                from admin import admin
                from historical_data import historical_data
                from suggestions import suggestions
                from chat import chat
                from routes import main
                from reports import reports
                from bank_statements import bank_statements

                # Register blueprints with proper URL prefixes
                blueprints = [
                    (auth, ''),
                    (admin, '/admin'),
                    (historical_data, ''),
                    (suggestions, ''),
                    (chat, '/chat'),
                    (main, ''),
                    (reports, '/reports'),
                    (bank_statements, '')
                ]

                for blueprint, url_prefix in blueprints:
                    try:
                        app.register_blueprint(blueprint, url_prefix=url_prefix)
                        logger.info(f"Registered blueprint: {blueprint.name}")
                    except Exception as e:
                        logger.error(f"Error registering blueprint {blueprint.name}: {str(e)}")
                        raise

                # Ensure database tables exist
                db.create_all()
                logger.info("Database tables verified")

                return app

            except Exception as e:
                logger.error(f"Error during application setup: {str(e)}")
                raise

    except Exception as e:
        logger.error(f"Critical error in application creation: {str(e)}")
        return None

def main():
    """Main entry point for the application"""
    try:
        app = create_app()
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