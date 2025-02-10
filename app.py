"""Main application factory with enhanced logging and protection"""
import os
import logging
from flask import Flask
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import text
from models import db, User
from sqlalchemy.exc import OperationalError, SQLAlchemyError

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

# Initialize Flask extensions
login_manager = LoginManager()
csrf = CSRFProtect()

def init_database(app):
    """Initialize database with proper error handling"""
    try:
        # Initialize SQLAlchemy
        db.init_app(app)

        # Test database connection
        with app.app_context():
            db.session.execute(text('SELECT 1'))
            db.session.commit()
            logger.info("Database connection successful")
            return True
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        return False

def create_app(config_name='development'):
    """Create and configure Flask application"""
    try:
        # Create Flask app
        app = Flask(__name__)

        # Load configuration
        if isinstance(config_name, str):
            app.config.from_object(f'config.{config_name.capitalize()}Config')
        else:
            app.config.update(config_name)

        # Ensure instance folder exists
        os.makedirs('instance', exist_ok=True)

        # Initialize extensions
        login_manager.init_app(app)
        csrf.init_app(app)
        login_manager.login_view = 'auth.login'
        login_manager.login_message = 'Please log in to access this page.'
        login_manager.login_message_category = 'info'

        # Initialize database
        if not init_database(app):
            # Try SQLite fallback
            sqlite_path = os.path.join(app.instance_path, 'dev.db')
            app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{sqlite_path}'
            logger.info(f"Attempting SQLite fallback at {sqlite_path}")

            if not init_database(app):
                raise Exception("Both PostgreSQL and SQLite initialization failed")

        # Initialize migrations
        Migrate(app, db)
        logger.info("Database migrations initialized")

        # Register blueprints
        logger.info("Registering blueprints...")
        from main import bp as main_bp
        app.register_blueprint(main_bp)

        from auth import bp as auth_bp
        app.register_blueprint(auth_bp)

        from admin import bp as admin_bp
        app.register_blueprint(admin_bp, url_prefix='/admin')

        from errors import bp as errors_bp
        app.register_blueprint(errors_bp)

        logger.info("Application initialization complete")
        return app

    except Exception as e:
        logger.error(f"Application creation failed: {str(e)}")
        return None

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login"""
    try:
        return User.query.get(int(user_id))
    except Exception as e:
        logger.error(f"Error loading user {user_id}: {str(e)}")
        return None

if __name__ == '__main__':
    app = create_app()
    if app:
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port)
    else:
        logger.error("Failed to create application")