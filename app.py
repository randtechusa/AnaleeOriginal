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

        # Configure Flask app
        config = {
            'SECRET_KEY': os.environ.get("FLASK_SECRET_KEY", os.urandom(24).hex()),
            'SQLALCHEMY_DATABASE_URI': database_url,
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
            'TEMPLATES_AUTO_RELOAD': True,
            'WTF_CSRF_ENABLED': True,
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

        # Initialize scheduler
        scheduler.init_app(app)
        scheduler.start()

        with app.app_context():
            # Register blueprints
            try:
                from routes import main as main_blueprint
                app.register_blueprint(main_blueprint)

                from reports import reports as reports_blueprint
                app.register_blueprint(reports_blueprint, url_prefix='/reports')

                # Register historical data blueprint (protected core feature)
                from historical_data import historical_data as historical_data_blueprint
                logger.info("Registering historical data blueprint with URL prefix: /historical-data")
                app.register_blueprint(historical_data_blueprint)

                # Register chat blueprint (protected core feature)
                from chat.routes import chat as chat_blueprint
                logger.info("Registering chat blueprint")
                app.register_blueprint(chat_blueprint)

                # Register error monitoring blueprint
                from errors import errors as errors_blueprint
                logger.info("Registering error monitoring blueprint")
                app.register_blueprint(errors_blueprint)

                # Register predictions blueprint
                from predictions.routes import predictions as predictions_blueprint
                logger.info("Registering predictions blueprint with URL prefix: /predictions")
                app.register_blueprint(predictions_blueprint, url_prefix='/predictions')

                # Register risk assessment blueprint
                from risk_assessment import risk_assessment as risk_assessment_blueprint
                logger.info("Registering risk assessment blueprint")
                app.register_blueprint(risk_assessment_blueprint)

                # Register recommendations blueprint
                from recommendations import recommendations as recommendations_blueprint
                logger.info("Registering recommendations blueprint")
                app.register_blueprint(recommendations_blueprint)

                # Register admin blueprint (new)
                logger.info("Registering admin blueprint")
                app.register_blueprint(admin_blueprint)

                # Create admin account if it doesn't exist
                def create_admin_account():
                    """Create the one-off admin account if it doesn't exist"""
                    admin_email = "festusa@cnbs.co.za"
                    admin = User.query.filter_by(email=admin_email).first()
                    if not admin:
                        admin = User(
                            username="admin",
                            email=admin_email,
                            is_admin=True,
                            subscription_status='active'
                        )
                        admin.set_password("Fes5036tus@3")
                        db.session.add(admin)
                        db.session.commit()
                        logger.info("Admin account created successfully")
                    else:
                        logger.info("Admin account already exists")

                try:
                    create_admin_account()
                except Exception as e:
                    logger.error(f"Error creating admin account: {str(e)}")

                logger.info("All blueprints registered successfully")
            except Exception as blueprint_error:
                logger.error(f"Error registering blueprints: {str(blueprint_error)}")
                raise

            logger.info("Application initialization completed successfully")
            return app

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