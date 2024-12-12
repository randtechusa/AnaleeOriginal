import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from dotenv import load_dotenv
import sys

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Initialize Flask extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()

def create_app():
    """Create and configure the Flask application"""
    try:
        app = Flask(__name__)
        logger.info("Starting Flask application initialization...")
        
        # Configure Flask application
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            logger.error("DATABASE_URL environment variable is not set")
            raise ValueError("DATABASE_URL environment variable is not set")

        # Handle legacy database URLs
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        
        # Configure Flask app
        app.config.update(
            SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", os.urandom(24).hex()),
            SQLALCHEMY_DATABASE_URI=database_url,
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TEMPLATES_AUTO_RELOAD=True,
        )
        logger.debug("Flask app configuration completed")

        # Initialize Flask extensions
        db.init_app(app)
        migrate.init_app(app, db)
        login_manager.init_app(app)
        login_manager.login_view = 'main.login'
        logger.debug("Flask extensions initialized")

        with app.app_context():
            # Import models here to avoid circular imports
            from models import User, Account, Transaction, UploadedFile, CompanySettings
            logger.debug("Models imported")

            try:
                # Initialize database
                db.create_all()
                logger.debug("Database tables created")
                
                # Register blueprints
                from routes import main as main_blueprint
                app.register_blueprint(main_blueprint)
                logger.debug("Blueprints registered")
                
                return app
                
            except Exception as db_error:
                logger.error(f"Database initialization error: {str(db_error)}")
                raise

    except Exception as e:
        logger.error(f"Error during app creation: {str(e)}")
        logger.exception("Full stack trace:")
        raise
