"""Main application factory with enhanced database management"""
import os
import logging
from flask import Flask, current_app
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import text
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
from sqlalchemy.exc import OperationalError, SQLAlchemyError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[logging.FileHandler('app.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Initialize Flask extensions
login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()

def init_database(app):
    """Initialize database with retry mechanism"""
    logger.info("Initializing database...")
    
    try:
        db.init_app(app)
        with app.app_context():
            db.create_all()
            db.session.execute(text('SELECT 1'))
            db.session.commit()
            logger.info("Database connection test successful")
            return True
            
    except OperationalError as e:
        logger.warning(f"Database connection failed: {str(e)}")
        # Configure SQLite fallback
        sqlite_path = os.path.join(app.instance_path, 'dev.db')
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{sqlite_path}'
        os.makedirs(app.instance_path, exist_ok=True)

        try:
            with app.app_context():
                # Clear existing binds and dispose engine
                if hasattr(db, 'session'):
                    db.session.remove()
                if hasattr(db, 'engine') and db.engine:
                    db.engine.dispose()

                # Initialize with SQLite
                db.init_app(app)
                db.create_all()
                logger.info("Successfully initialized SQLite fallback database")
                return True

        except Exception as sqlite_error:
            logger.error(f"SQLite fallback failed: {str(sqlite_error)}")
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
            
        # Ensure SQLALCHEMY_DATABASE_URI is set
        if not app.config.get('SQLALCHEMY_DATABASE_URI'):
            app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/dev.db'
            app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

        # Ensure SQLALCHEMY_DATABASE_URI is set
        if 'SQLALCHEMY_DATABASE_URI' not in app.config:
            app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
            app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

        # Set up extensions
        login_manager.init_app(app)
        csrf.init_app(app)

        # Configure login views
        login_manager.login_view = 'auth.login'
        login_manager.login_message = 'Please log in to access this page.'
        login_manager.login_message_category = 'info'

        with app.app_context():
            # Initialize database
            if not init_database(app):
                logger.error("Failed to initialize database")
                return None

            # Initialize migrations
            migrate.init_app(app, db)

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
        return User.query.get(int(user_id))
    except Exception as e:
        logger.error(f"Error loading user {user_id}: {str(e)}")
        return None

if __name__ == '__main__':
    app = create_app('production')
    if app:
        app.run(host='0.0.0.0', port=5000, debug=False)
    else:
        logger.error("Failed to create application")