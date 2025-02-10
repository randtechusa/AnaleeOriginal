"""Main application factory with enhanced logging and protection"""
import os
import logging
from flask import Flask, render_template
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import text
from models import db, User
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from tenacity import retry, stop_after_attempt, wait_exponential

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

        # Load configuration
        if isinstance(config_name, str):
            app.config.from_object(f'config.{config_name.capitalize()}Config')
        else:
            app.config.update(config_name)

        # Ensure instance folder exists
        if not os.path.exists('instance'):
            os.makedirs('instance')

        # Initialize extensions
        db.init_app(app)
        Migrate(app, db)
        login_manager.init_app(app)
        csrf.init_app(app)

        login_manager.login_view = 'auth.login'
        login_manager.login_message = 'Please log in to access this page.'
        login_manager.login_message_category = 'info'

        with app.app_context():
            try:
                # Test database connection
                db.session.execute(text('SELECT 1'))
                db.session.commit()
                logger.info("Database connection successful")

                # Create tables if they don't exist
                db.create_all()
                logger.info("Database tables created successfully")
            except OperationalError as e:
                logger.error(f"Database connection error: {str(e)}")
                # Configure SQLite fallback
                sqlite_path = os.path.join(app.instance_path, 'dev.db')
                app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{sqlite_path}'

                # Ensure instance folder exists
                if not os.path.exists(app.instance_path):
                    os.makedirs(app.instance_path)

                # Reinitialize database with SQLite
                db.create_all()
                logger.info("Created SQLite database as fallback")

        # Register blueprints
        logger.info("Registering blueprints...")

        # Main blueprint
        from main import bp as main_bp
        app.register_blueprint(main_bp)
        logger.info("Registered main blueprint")

        # Auth blueprint
        from auth import bp as auth_bp
        app.register_blueprint(auth_bp)
        logger.info("Registered auth blueprint")

        # Admin blueprint
        from admin import bp as admin_bp
        app.register_blueprint(admin_bp, url_prefix='/admin')
        logger.info("Registered admin blueprint")

        # Errors blueprint
        from errors import bp as errors_bp
        app.register_blueprint(errors_bp)
        logger.info("Registered errors blueprint")

        return app

    except Exception as e:
        logger.error(f"Application creation failed: {str(e)}")
        raise

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
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)