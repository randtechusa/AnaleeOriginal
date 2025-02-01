"""Main application factory with enhanced logging and protection"""
import os
import logging
from datetime import datetime
from flask import Flask, render_template, request
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from models import db, User
from config import config

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[logging.FileHandler('app.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

login_manager = LoginManager()
csrf = CSRFProtect()

def create_app(config_name='development'):
    """Create and configure Flask application"""
    try:
        app = Flask(__name__, instance_relative_config=True)
        app.config.from_object(config[config_name])

        # Ensure proper database URL format
        if app.config['SQLALCHEMY_DATABASE_URI'] and app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
            app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)

        logger.info(f"Using database URL: {app.config['SQLALCHEMY_DATABASE_URI']}")

        # Initialize extensions
        db.init_app(app)
        Migrate(app, db)
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

            app.register_blueprint(auth)
            app.register_blueprint(main)
            app.register_blueprint(historical_data)
            app.register_blueprint(bank_statements)
            app.register_blueprint(reports)
            app.register_blueprint(chat)
            app.register_blueprint(admin)
            app.register_blueprint(errors)

            # Create database tables
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

if __name__ == '__main__':
    try:
        app = create_app('development')
        port = int(os.environ.get('PORT', 5000))
        app.run(
            host='0.0.0.0',
            port=port,
            debug=True
        )
    except Exception as e:
        logger.error(f"Error running application: {str(e)}")