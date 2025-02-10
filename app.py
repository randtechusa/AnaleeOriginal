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

    try:
        logger.info(f"Starting application with config: {config_name}")

        # Load configuration
        app.config.from_object('config.DevelopmentConfig')

        # Basic Configuration
        app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24).hex())
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

        # Database Configuration
        if os.environ.get('DATABASE_URL'):
            db_url = os.environ.get('DATABASE_URL')
            if db_url.startswith('postgres://'):
                db_url = db_url.replace('postgres://', 'postgresql://', 1)
            app.config['SQLALCHEMY_DATABASE_URI'] = db_url
            app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
                'pool_pre_ping': True,
                'pool_size': 1,
                'max_overflow': 0,
                'pool_recycle': 1800
            }
        else:
            # SQLite fallback
            sqlite_path = os.path.join(app.instance_path, 'dev.db')
            os.makedirs(app.instance_path, exist_ok=True)
            app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{sqlite_path}'
            app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
                'pool_pre_ping': True
            }
            logger.info(f"Using SQLite database at: {sqlite_path}")

        # Error handlers
        @app.errorhandler(500)
        def internal_error(error):
            logger.error(f"Internal Server Error: {error}")
            db.session.rollback()
            return render_template('error.html', error="An internal error occurred. Please try again."), 500

        @app.errorhandler(404)
        def not_found_error(error):
            return render_template('error.html', error="Page not found"), 404

        # Initialize extensions
        logger.debug("Initializing Flask extensions...")
        db.init_app(app)
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

        # Root route
        @app.route('/')
        def index():
            return render_template('index.html')

        # Initialize database
        with app.app_context():
            try:
                logger.debug("Testing database connection...")
                db.session.execute(text('SELECT 1'))
                logger.debug("Creating database tables...")
                db.create_all()
                logger.info("Database initialized successfully")
            except Exception as e:
                logger.error(f"Database initialization error: {str(e)}")
                if 'sqlite' not in app.config['SQLALCHEMY_DATABASE_URI']:
                    logger.info("Switching to SQLite fallback database")

                    # Close any existing connections
                    db.session.remove()

                    # Configure SQLite
                    sqlite_path = os.path.join('instance', 'dev.db')
                    os.makedirs('instance', exist_ok=True)
                    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{sqlite_path}'
                    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
                        'pool_pre_ping': True
                    }

                    try:
                        db.create_all()
                        logger.info(f"Successfully initialized SQLite database at {sqlite_path}")
                    except Exception as sqlite_err:
                        logger.error(f"SQLite fallback failed: {str(sqlite_err)}")
                        raise

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