"""Main application factory with enhanced database management"""
import os
import logging
from flask import Flask, current_app
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import text
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import OperationalError, SQLAlchemyError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[logging.FileHandler('app.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Initialize Flask extensions
db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()

def init_database(app, db_instance):
    """Initialize database with comprehensive error handling"""
    logger.info("Initializing database...")

    try:
        # Ensure instance directory exists
        os.makedirs('instance', exist_ok=True)

        # Configure SQLAlchemy settings
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

        # Initialize database
        db_instance.init_app(app)

        # Test connection
        with app.app_context():
            db_instance.create_all()
            try:
                db_instance.session.execute(text('SELECT 1'))
                db_instance.session.commit()
                logger.info("Database connection successful")
                return True
            except Exception as e:
                logger.error(f"Database connection test failed: {str(e)}")
                return False

    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        return False

def create_app(config_name='development'):
    """Create and configure Flask application"""
    app = Flask(__name__)

    try:
        # Load configuration
        if isinstance(config_name, str):
            app.config.from_object(f'config.{config_name.capitalize()}Config')
        else:
            app.config.update(config_name)

        # Ensure instance directory exists
        os.makedirs(app.instance_path, exist_ok=True)

        # Set up extensions
        login_manager.init_app(app)
        csrf.init_app(app)

        # Configure login views
        login_manager.login_view = 'auth.login'
        login_manager.login_message = 'Please log in to access this page.'
        login_manager.login_message_category = 'info'

        # Initialize database
        if not init_database(app, db):
            logger.error("Failed to initialize database")
            return None

        # Initialize migrations
        migrate.init_app(app, db)

        # Register blueprints
        from main import bp as main_bp
        app.register_blueprint(main_bp)

        from auth import bp as auth_bp
        app.register_blueprint(auth_bp)

        from admin import bp as admin_bp
        app.register_blueprint(admin_bp, url_prefix='/admin')

        from errors import bp as errors_bp
        app.register_blueprint(errors_bp)

        logger.info("Application initialization completed successfully")
        return app

    except Exception as e:
        logger.error(f"Application creation failed: {str(e)}")
        return None

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login"""
    if not current_app:
        return None

    try:
        from models import User
        return User.query.get(int(user_id))
    except Exception as e:
        logger.error(f"Error loading user {user_id}: {str(e)}")
        return None

if __name__ == '__main__':
    app = create_app('development')
    if app:
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port)
    else:
        logger.error("Failed to create application")