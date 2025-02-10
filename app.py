"""Main application factory with enhanced logging and protection"""
import os
import time
import logging
from datetime import datetime
from flask import Flask, render_template, request
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy import text
from models import db, User

# Import blueprints
from auth import auth
from admin import admin
from chat import chat
from errors import errors
from historical_data import historical_data
from recommendations import recommendations
from risk_assessment import risk_assessment
from reports import reports
from suggestions import suggestions

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
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
    app.config.from_object('config.Config')
    db.init_app(app)
    with app.app_context():
        db.create_all()


    try:
        logger.info(f"Starting application with config: {config_name}")


        # Load environment-specific configuration
        config_class = f'config.{config_name.capitalize()}Config'
        app.config.from_object(config_class)


        logger.debug("Initializing Flask extensions...")
        migrate = Migrate(app, db)
        login_manager.init_app(app)
        csrf.init_app(app)

        login_manager.login_view = 'auth.login'

        # Register blueprints
        logger.debug("Registering blueprints...")
        app.register_blueprint(auth)
        app.register_blueprint(admin)
        app.register_blueprint(chat)
        app.register_blueprint(errors)
        app.register_blueprint(historical_data)
        app.register_blueprint(recommendations)
        app.register_blueprint(risk_assessment)
        app.register_blueprint(reports)
        app.register_blueprint(suggestions)

        # Error handlers
        @app.errorhandler(500)
        def internal_error(error):
            logger.error(f"Internal Server Error: {error}")
            db.session.rollback()
            return render_template('error.html', error="An internal error occurred. Please try again."), 500

        @app.errorhandler(404)
        def not_found_error(error):
            return render_template('error.html', error="Page not found"), 404

        # Root route
        @app.route('/')
        def index():
            return render_template('index.html')


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
    app.run(host='0.0.0.0', port=5000, debug=True)