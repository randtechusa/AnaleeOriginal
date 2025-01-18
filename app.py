"""Main application factory with enhanced logging and protection"""
import os
import logging
import time
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential
from flask import Flask, render_template
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from models import db, User
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from config import config

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask extensions
login_manager = LoginManager()
csrf = CSRFProtect()

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True
)
def test_db_connection(db_url):
    """Test database connection with retry logic"""
    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        logger.info("Database connection test successful")
        return True
    except Exception as e:
        logger.error(f"Database connection test failed: {str(e)}")
        raise

def create_app(config_name='development'):
    """Create and configure Flask application with enhanced logging"""
    app = Flask(__name__, instance_relative_config=True)

    # Load configuration
    logger.info(f"Starting application with {config_name} configuration...")
    app.config.from_object(config[config_name])

    # Ensure instance folder exists
    try:
        os.makedirs(app.instance_path, exist_ok=True)
        logger.info(f"Instance folder created at {app.instance_path}")
    except Exception as e:
        logger.error(f"Failed to create instance folder: {str(e)}")
        raise

    # Initialize extensions
    logger.info("Initializing Flask extensions...")
    db.init_app(app)
    migrate = Migrate(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    csrf.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        """Load user by ID"""
        try:
            return User.query.get(int(user_id))
        except Exception as e:
            logger.error(f"Error loading user {user_id}: {str(e)}")
            return None

    # Register blueprints
    with app.app_context():
        logger.info("Registering blueprints...")
        from auth.routes import auth
        from main.routes import main
        from historical_data import historical_data
        from bank_statements import bank_statements
        from reports import reports
        from chat import chat
        from errors import errors

        # Core protected modules
        blueprints = [
            (auth, "Authentication"),
            (main, "Main Application"),
            (historical_data, "Historical Data"),
            (bank_statements, "Bank Statements"),
            (reports, "Reports"),
            (chat, "Chat"),
            (errors, "Error Handling")
        ]

        for blueprint, name in blueprints:
            try:
                app.register_blueprint(blueprint)
                logger.info(f"Registered {name} blueprint")
            except Exception as e:
                logger.error(f"Failed to register {name} blueprint: {str(e)}")
                raise

        # Initialize database tables
        try:
            logger.info("Creating database tables if they don't exist...")
            db.create_all()
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating database tables: {str(e)}")
            raise

    # Error handlers
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        logger.error(f"Internal Server Error: {str(error)}")
        return render_template('error.html', error=error), 500

    @app.errorhandler(Exception)
    def handle_exception(error):
        db.session.rollback()
        logger.error(f"Unhandled Exception: {str(error)}", exc_info=True)
        return render_template('error.html', error=error), 500

    logger.info("Application creation completed successfully")
    return app

if __name__ == '__main__':
    app = create_app(os.getenv('FLASK_ENV', 'development'))
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)