import os
import logging
from flask import Flask, render_template, request, session
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from models import db, User

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask extensions 
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect() # Added CSRF protection

def create_app():
    """Create and configure Flask application with enhanced logging"""
    logger.info("Starting application creation...")
    app = Flask(__name__)

    # Basic configuration with logging
    logger.info("Configuring application with database connection...")

    # Database configuration with retries
    max_retries = 5
    retry_count = 0
    while retry_count < max_retries:
        try:
            db_url = os.environ.get('DEV_DATABASE_URL', 'sqlite:///app.db')
            app.config['SQLALCHEMY_DATABASE_URI'] = db_url
            app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
            app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(32))
            app.config['WTF_CSRF_ENABLED'] = True # Added CSRF config
            app.config['SESSION_COOKIE_SECURE'] = True # Added session config
            app.config['SESSION_COOKIE_HTTPONLY'] = True # Added session config

            # Test database connection
            db.init_app(app)
            with app.app_context():
                try:
                    db.engine.connect()
                    db.engine.dispose()
                except Exception as e:
                    logger.error(f"Database connection error: {str(e)}")
                    raise
            logger.info("Database connection verified")
            break

        except Exception as e:
            retry_count += 1
            logger.warning(f"Database connection attempt {retry_count} failed: {str(e)}")
            if retry_count == max_retries:
                logger.error(f"Database connection failed after {max_retries} attempts: {str(e)}")
                logger.error("Failed to establish database connection")
                raise

    # Initialize other extensions
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    csrf.init_app(app) # Initialize CSRF protection

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return User.query.get(int(user_id))
        except Exception as e:
            logger.error(f"Error loading user {user_id}: {str(e)}")
            return None

    # Register blueprints with error handling
    from auth.routes import auth
    from main.routes import main

    app.register_blueprint(auth)
    app.register_blueprint(main)

    logger.info("All blueprints registered successfully")

    # Verify database tables
    with app.app_context():
        try:
            db.create_all()
            logger.info("Database tables verified")
        except Exception as e:
            logger.error(f"Error verifying database tables: {str(e)}")
            raise

    # Register error handlers
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()  # Roll back any failed database transactions
        logger.error(f"Internal Server Error: {str(error)}")
        return render_template('error.html', error=error), 500

    @app.errorhandler(Exception)
    def handle_exception(error):
        db.session.rollback()
        logger.error(f"Unhandled Exception: {str(error)}")
        return render_template('error.html', error=error), 500

    logger.info("Flask application created successfully")
    return app

if __name__ == '__main__':
    app = create_app()
    logger.info("Starting Flask server on port 5000")
    app.run(host='0.0.0.0', port=5000)