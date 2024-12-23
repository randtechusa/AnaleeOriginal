import os
import logging
import sys
from datetime import datetime
from flask import Flask, current_app
from flask_migrate import Migrate 
from dotenv import load_dotenv
from sqlalchemy import text
from flask_apscheduler import APScheduler
from flask_wtf.csrf import CSRFProtect
from models import db, login_manager, User, Account, Transaction, CompanySettings, UploadedFile, HistoricalData
from admin import admin as admin_blueprint

# Configure logging with more detailed error reporting
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log')
    ]
)

# Create module logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Load environment variables
load_dotenv()

# Initialize Flask extensions
migrate = Migrate()
scheduler = APScheduler()
csrf = CSRFProtect()

def create_app(env=os.environ.get('FLASK_ENV', 'production')):
    """Create and configure the Flask application"""
    try:
        # Initialize Flask application
        app = Flask(__name__)

        # Load the appropriate configuration
        app.config.from_object(f'config.{env.capitalize()}Config')

        # Get appropriate database URL based on environment
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            logger.error("Database URL is not set")
            return None

        # Handle legacy database URL format
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)

        # Configure Flask app with enhanced security
        config = {
            'SECRET_KEY': os.environ.get("FLASK_SECRET_KEY", os.urandom(24).hex()),
            'SQLALCHEMY_DATABASE_URI': database_url,
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
            'TEMPLATES_AUTO_RELOAD': True,
            'WTF_CSRF_ENABLED': True,
            'WTF_CSRF_SECRET_KEY': os.environ.get("WTF_CSRF_SECRET_KEY", os.urandom(24).hex()),
            'WTF_CSRF_TIME_LIMIT': 3600,  # 1 hour CSRF token validity
            'SQLALCHEMY_ENGINE_OPTIONS': {
                'pool_pre_ping': True,
                'pool_size': 5,
                'pool_timeout': 30,
                'pool_recycle': 300,
                'max_overflow': 2
            }
        }

        app.config.update(config)
        logger.debug("Flask app configuration completed")

        # Initialize Flask extensions
        db.init_app(app)
        migrate.init_app(app, db)
        login_manager.init_app(app)
        csrf.init_app(app)  # Initialize CSRF protection
        login_manager.login_view = 'main.login'

        # Initialize scheduler with error handling
        try:
            scheduler.init_app(app)
            scheduler.start()
            logger.info("Scheduler initialized successfully")
        except Exception as scheduler_error:
            logger.error(f"Error initializing scheduler: {str(scheduler_error)}")
            # Continue without scheduler - non-critical component

        with app.app_context():
            # Register blueprints with proper error handling
            try:
                # Core blueprints - protected components
                from routes import main as main_blueprint
                app.register_blueprint(main_blueprint)
                logger.info("Main blueprint registered successfully")

                from reports import reports as reports_blueprint
                app.register_blueprint(reports_blueprint, url_prefix='/reports')
                logger.info("Reports blueprint registered successfully")

                # Historical data blueprint (protected core feature)
                from historical_data import historical_data as historical_data_blueprint
                app.register_blueprint(historical_data_blueprint, url_prefix='/historical-data')
                logger.info("Historical data blueprint registered successfully")

                # Chat blueprint (protected core feature)
                from chat.routes import chat as chat_blueprint
                app.register_blueprint(chat_blueprint, url_prefix='/chat')
                logger.info("Chat blueprint registered successfully")

                # Error monitoring blueprint
                from errors import errors as errors_blueprint
                app.register_blueprint(errors_blueprint)
                logger.info("Error monitoring blueprint registered successfully")

                # Predictions blueprint
                from predictions.routes import predictions as predictions_blueprint
                app.register_blueprint(predictions_blueprint, url_prefix='/predictions')
                logger.info("Predictions blueprint registered successfully")

                # Risk assessment blueprint
                from risk_assessment import risk_assessment as risk_assessment_blueprint
                app.register_blueprint(risk_assessment_blueprint, url_prefix='/risk')
                logger.info("Risk assessment blueprint registered successfully")

                # Recommendations blueprint
                from recommendations import recommendations as recommendations_blueprint
                app.register_blueprint(recommendations_blueprint, url_prefix='/recommendations')
                logger.info("Recommendations blueprint registered successfully")

                # Admin blueprint (new)
                logger.info("Registering admin blueprint")
                app.register_blueprint(admin_blueprint, url_prefix='/admin')

                logger.info("All blueprints registered successfully")

                # Verify database connection before proceeding
                try:
                    with db.engine.connect() as connection:
                        connection.execute(text("SELECT 1"))
                    logger.info("Database connection verified")
                except Exception as db_error:
                    logger.error(f"Database connection error: {str(db_error)}")
                    return None

                return app

            except Exception as blueprint_error:
                logger.error(f"Error registering blueprints: {str(blueprint_error)}")
                return None

    except Exception as e:
        logger.error(f"Critical error in application creation: {str(e)}")
        return None

if __name__ == '__main__':
    try:
        # Initialize the application
        logger.info("Starting application initialization...")
        app = create_app()

        if not app:
            logger.error("Application creation failed")
            sys.exit(1)

        # Get port and configure server
        port = int(os.environ.get('PORT', 5000))
        logger.info(f"Configuring server to run on port {port}")

        # Start the server
        logger.info(f"Starting Flask application on http://0.0.0.0:{port}")
        app.run(
            host='0.0.0.0',
            port=port,
            debug=True,  # Enable debug mode
            use_reloader=False  # Disable reloader to prevent duplicate processes
        )
    except Exception as e:
        logger.error(f"Critical error starting application: {str(e)}")
        logger.exception("Full stack trace:")
        sys.exit(1)