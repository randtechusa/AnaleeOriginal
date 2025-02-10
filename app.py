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

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=20),
    reraise=True
)
def init_database(app):
    """Initialize database with enhanced SQLite fallback"""
    try:
        logger.info("Initializing database connection...")
        with app.app_context():
            try:
                if 'postgres' in app.config['SQLALCHEMY_DATABASE_URI']:
                    # Test PostgreSQL connection
                    db.session.execute(text('SELECT 1'))
                    db.session.commit()
                    logger.info("PostgreSQL connection successful")
            except OperationalError as e:
                logger.warning(f"PostgreSQL connection failed: {str(e)}")
                logger.info("Configuring SQLite database")
                
                # Close existing connections
                db.session.remove()
                db.engine.dispose()
                
                # Configure SQLite
                sqlite_path = os.path.join(app.instance_path, 'dev.db')
                app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{sqlite_path}'
                
                # Ensure instance folder exists
                if not os.path.exists(app.instance_path):
                    os.makedirs(app.instance_path)
                
                # Reinitialize SQLAlchemy
                db.init_app(app)
            
            # Create tables
            db.create_all()
            logger.info("Database tables created successfully")
            return True
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        return False

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

        # Initialize database with retry logic
        init_database(app)

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

        # Register error handlers
        @app.errorhandler(404)
        def not_found_error(error):
            logger.warning(f"404 error: {error}")
            return render_template('error.html', error="Page not found"), 404

        @app.errorhandler(500)
        def internal_error(error):
            logger.error(f"Internal Server Error: {error}")
            db.session.rollback()
            return render_template('error.html', error="An internal error occurred."), 500

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