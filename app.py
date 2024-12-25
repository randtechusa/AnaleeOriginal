import os
import logging
import sys
from flask import Flask
from flask_migrate import Migrate
from dotenv import load_dotenv
from sqlalchemy import text
from flask_wtf.csrf import CSRFProtect
from models import db, login_manager

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log')
    ]
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Load environment variables
load_dotenv()

# Initialize Flask extensions
migrate = Migrate()
csrf = CSRFProtect()

def create_app():
    """Create and configure the Flask application"""
    try:
        # Initialize Flask application
        app = Flask(__name__)

        # Get database URL from environment
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            logger.error("DATABASE_URL is not set")
            return None

        # Handle legacy database URL format
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)

        # Basic configuration
        app.config.update({
            'SECRET_KEY': os.environ.get("FLASK_SECRET_KEY", os.urandom(24).hex()),
            'SQLALCHEMY_DATABASE_URI': database_url,
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
            'WTF_CSRF_ENABLED': True,
            'TEMPLATES_AUTO_RELOAD': True
        })

        # Initialize extensions
        db.init_app(app)
        migrate.init_app(app, db)
        csrf.init_app(app)
        login_manager.init_app(app)
        login_manager.login_view = 'auth.login'

        # Test database connection
        with app.app_context():
            try:
                db.session.execute(text('SELECT 1'))
                logger.info("Database connection successful")

                # Register all blueprints
                from auth import auth as auth_blueprint
                from main import main as main_blueprint
                from bank_statements import bank_statements as bank_statements_blueprint
                from historical_data import historical_data as historical_data_blueprint
                from reports import reports as reports_blueprint
                from risk_assessment import risk_assessment as risk_assessment_blueprint
                from recommendations import recommendations as recommendations_blueprint
                from errors import errors as errors_blueprint
                from admin import admin as admin_blueprint

                app.register_blueprint(auth_blueprint, url_prefix='/auth')
                app.register_blueprint(main_blueprint)
                app.register_blueprint(bank_statements_blueprint)
                app.register_blueprint(historical_data_blueprint)
                app.register_blueprint(reports_blueprint)
                app.register_blueprint(risk_assessment_blueprint)
                app.register_blueprint(recommendations_blueprint)
                app.register_blueprint(errors_blueprint)
                app.register_blueprint(admin_blueprint, url_prefix='/admin')

                logger.info("All blueprints registered successfully")
                return app

            except Exception as e:
                logger.error(f"Database connection failed: {str(e)}")
                return None

    except Exception as e:
        logger.error(f"Error creating Flask application: {str(e)}")
        return None

if __name__ == '__main__':
    app = create_app()
    if not app:
        logger.error("Failed to create Flask application")
        sys.exit(1)

    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting Flask server on port {port}")

    app.run(
        host='0.0.0.0',
        port=port,
        debug=True
    )