"""Main application factory with enhanced database management"""
import os
import logging
import time
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
    max_retries = 10  # Increased retries for Neon serverless
    retry_count = 0
    base_delay = 1  # Start with shorter delay

    if not app.config['SQLALCHEMY_DATABASE_URI']:
        logger.error("DATABASE_URL environment variable is not set")
        return False

    # Verify database URL format
    if 'neon.tech' in app.config['SQLALCHEMY_DATABASE_URI']:
        logger.info("Using Neon database, verifying endpoint...")

    # Check if database URL is configured
    if not app.config['SQLALCHEMY_DATABASE_URI']:
        logger.error("DATABASE_URL environment variable is not set")
        return False

    # Convert database URL to use connection pooler if needed
    if '.neon.tech' in app.config['SQLALCHEMY_DATABASE_URI']:
        app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('.neon.tech', '-pooler.neon.tech')
        logger.info("Using connection pooler URL")

    while retry_count < max_retries:
        try:
            with app.app_context():
                logger.info("Verifying database connection...")

                # Log database configuration (without sensitive info)
                db_url_parts = app.config['SQLALCHEMY_DATABASE_URI'].split('@')
                if len(db_url_parts) > 1:
                    safe_db_url = f"postgresql://[username]@{db_url_parts[1]}"
                    logger.info(f"Using database URL: {safe_db_url}")

                # Test database connection
                db.session.execute(text('SELECT 1'))
                db.session.commit()

                logger.info("Database connection successful")
                logger.info("Creating database tables...")
                db.create_all()
                logger.info("Database initialization completed successfully")
                return True

        except Exception as e:
            retry_count += 1
            delay = min(base_delay * (2 ** (retry_count - 1)), 10)  # Exponential backoff, max 10 seconds

            logger.warning(
                f"Database initialization attempt {retry_count} failed: {str(e)}\n"
                f"Retrying in {delay} seconds..."
            )

            if retry_count >= max_retries:
                logger.error("Database initialization failed after maximum retries", exc_info=True)
                return False

            time.sleep(delay)

    return False

def create_app(config_name=None):
    """Create and configure Flask application"""
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')

    logger.info(f"Creating Flask application with config: {config_name}")

    try:
        app = Flask(__name__)

        # Load configuration
        logger.info("Loading configuration...")
        config = get_config(config_name)
        app.config.from_object(config)

        # Log database configuration (without credentials)
        db_url = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if db_url:
            safe_url = db_url.split('@')[-1] if '@' in db_url else 'No URL found'
            logger.info(f"Database host: {safe_url}")


        # Configure SQLAlchemy from environment variables
        if 'DATABASE_URL' in os.environ:
            app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
            app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
            app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
                'pool_size': 5,
                'max_overflow': 10,
                'pool_recycle': 1800,
                'pool_pre_ping': True,
                'pool_timeout': 30,
                'connect_args': {
                    'connect_timeout': 10,
                    'application_name': 'financial_intelligence_platform'
                }
            }
            logger.info("Database configuration updated from environment")

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
            # Register error routes first for proper error handling
            from errors import bp as errors_bp
            app.register_blueprint(errors_bp)

            # Register other blueprints
            from main import bp as main_bp
            app.register_blueprint(main_bp)

            from auth import bp as auth_bp
            app.register_blueprint(auth_bp, url_prefix='/auth')

            from admin import bp as admin_bp
            app.register_blueprint(admin_bp, url_prefix='/admin')

            from reports import reports as reports_bp
            app.register_blueprint(reports_bp, url_prefix='/reports')

            from risk_assessment import risk_assessment as risk_bp
            app.register_blueprint(risk_bp, url_prefix='/risk')

            from historical_data import historical_data as historical_bp
            app.register_blueprint(historical_bp, url_prefix='/historical')

            @app.route('/')
            def index():
                return redirect(url_for('main.index'))

        logger.info("Application initialization completed successfully")
        return app

    except Exception as e:
        logger.error(f"Application creation failed: {str(e)}", exc_info=True)
        return None

if __name__ == '__main__':
    app = create_app('production')
    if app:
        port = int(os.environ.get('PORT', 5000))
        logger.info(f"Starting Flask server on port {port}")
        app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
    else:
        logger.error("Failed to create application")