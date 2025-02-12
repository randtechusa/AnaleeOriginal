"""Main application factory with enhanced database management"""
import os
import logging
from flask import Flask, redirect, url_for
from sqlalchemy import text
from extensions import db, init_extensions
from config import get_config

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def init_database(app):
    """Initialize database with comprehensive error handling"""
    logger.info("Starting database initialization...")

    try:
        # Create instance directory if it doesn't exist
        instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
        os.makedirs(instance_path, exist_ok=True)
        logger.info(f"Instance directory ensured at: {instance_path}")

        # Initialize database
        with app.app_context():
            logger.info("Creating database tables...")
            db.create_all()

            # Verify connection
            logger.info("Verifying database connection...")
            db.session.execute(text('SELECT 1'))
            db.session.commit()

            logger.info("Database initialization completed successfully")
            return True

    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}", exc_info=True)
        return False

def create_app(config_name=os.getenv('FLASK_ENV', 'production')):
    """Create and configure Flask application"""
    logger.info(f"Creating Flask application with config: {config_name}")

    try:
        app = Flask(__name__)

        # Load configuration
        logger.info("Loading configuration...")
        app.config.from_object(get_config(config_name))

        # Initialize extensions
        logger.info("Initializing Flask extensions...")
        init_extensions(app)

        # Initialize database
        if not init_database(app):
            logger.error("Database initialization failed")
            return None

        # Register blueprints
        logger.info("Registering blueprints...")
        with app.app_context():
            # Register main blueprint (no prefix for main routes)
            from main import bp as main_bp
            app.register_blueprint(main_bp)  # No prefix for main routes

            # Register auth blueprint
            from auth import bp as auth_bp
            app.register_blueprint(auth_bp, url_prefix='/auth')

            # Register admin blueprint
            from admin import bp as admin_bp
            app.register_blueprint(admin_bp, url_prefix='/admin')

            # Register errors blueprint
            from errors import bp as errors_bp
            app.register_blueprint(errors_bp)

            # Register reports blueprint
            from reports import reports as reports_bp
            app.register_blueprint(reports_bp, url_prefix='/reports')

            # Register risk assessment blueprint
            from risk_assessment import risk_assessment as risk_bp
            app.register_blueprint(risk_bp, url_prefix='/risk')

            # Register historical data blueprint
            from historical_data import historical_data as historical_bp
            app.register_blueprint(historical_bp, url_prefix='/historical')

            # Root route redirects to main blueprint's index
            @app.route('/')
            def index():
                logger.debug("Redirecting root to main.index")
                return redirect(url_for('main.index'))

        logger.info("Application initialization completed successfully")
        return app

    except Exception as e:
        logger.error(f"Application creation failed: {str(e)}", exc_info=True)
        return None

if __name__ == '__main__':
    app = create_app()
    if app:
        port = int(os.environ.get('PORT', 5000))
        logger.info(f"Starting Flask server on port {port}")
        app.run(host='0.0.0.0', port=port)
    else:
        logger.error("Failed to create application")