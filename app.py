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
    level=logging.DEBUG,  # Changed to DEBUG for more detailed logs
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
    
    # Load configuration
    app.config.from_object(f'config.{config_name.capitalize()}Config')
    app.config['DEBUG'] = True
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal Server Error: {error}")
        db.session.rollback()  # Roll back any failed database transactions
        return render_template('error.html', error="An internal error occurred. Please try again."), 500
        
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('error.html', error="Page not found"), 404

    try:
        logger.info(f"Starting application with config: {config_name}")

        # Basic Configuration
        app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24).hex())
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

        # Default to SQLite for development
        sqlite_path = os.path.join(app.instance_path, 'dev.db')
        os.makedirs(app.instance_path, exist_ok=True)
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{sqlite_path}'
        logger.info(f"Using SQLite database at: {sqlite_path}")

        # Initialize extensions with detailed logging
        logger.debug("Initializing Flask extensions...")
        db.init_app(app)
        migrate = Migrate(app, db)
        login_manager.init_app(app)
        csrf.init_app(app)

        login_manager.login_view = 'auth.login'

        # Register blueprints with logging
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

        # Initialize database with enhanced error handling
        with app.app_context():
            try:
                logger.debug("Testing database connection...")
                db.session.execute(text('SELECT 1'))
                logger.debug("Creating database tables...")
                db.create_all()
                logger.info("Database initialized successfully")
            except Exception as e:
                logger.warning(f"Primary database connection failed: {str(e)}")
                logger.info("Switching to SQLite fallback database")
                
                # Ensure instance directory exists
                if not os.path.exists('instance'):
                    os.makedirs('instance')
                
                # Configure SQLite
                sqlite_path = os.path.join('instance', 'dev.db')
                app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{sqlite_path}'
                
                try:
                    db.session.remove()  # Close any existing connections
                    db.create_all()  # Create tables in SQLite
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
    app.run(host='0.0.0.0', port=5000, debug=False)