import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from dotenv import load_dotenv
import os
import logging
from datetime import datetime

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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
        logger.debug("Flask app instance created")
        
        # Configure Flask application
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            logger.error("DATABASE_URL environment variable is not set")
            raise ValueError("DATABASE_URL environment variable is not set")

        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        logger.debug(f"Using database URL schema: {database_url.split('://')[0]}")

        # Test database connection before configuring app
        try:
            from sqlalchemy import create_engine, text
            test_engine = create_engine(database_url)
            with test_engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.scalar()
            logger.info("Database connection test successful")
        except Exception as db_test_error:
            logger.error(f"Failed to connect to database: {str(db_test_error)}")
            raise

        # Configure Flask app
        app.config.update(
            SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", os.urandom(24).hex()),
            SQLALCHEMY_DATABASE_URI=database_url,
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            SQLALCHEMY_ENGINE_OPTIONS={
                "pool_recycle": 300,
                "pool_pre_ping": True,
                "connect_args": {
                    "connect_timeout": 10
                }
            }
        )
        logger.debug("Flask app configuration completed")

        # Initialize Flask extensions
        logger.debug("Initializing Flask extensions")
        db.init_app(app)
        logger.debug("SQLAlchemy initialized")
        migrate.init_app(app, db)
        logger.debug("Flask-Migrate initialized")
        login_manager.init_app(app)
        login_manager.login_view = 'main.login'
        logger.debug("Login manager initialized")

        with app.app_context():
            # Import models
            logger.debug("Importing models...")
            from models import User, Account, Transaction, UploadedFile, CompanySettings
            logger.info("Models imported successfully")
            
            # Register blueprints
            logger.debug("Registering blueprints...")
            from routes import main as main_blueprint
            app.register_blueprint(main_blueprint)
            logger.info("Blueprints registered successfully")
            
            # Initialize database
            logger.debug("Testing database connection...")
            db.engine.connect()
            logger.info("Database connection successful")
            
            # Create all tables
            logger.debug("Creating database tables...")
            db.create_all()
            logger.info("Database tables created/verified successfully")
            
            # Run migrations
            try:
                logger.debug("Applying database migrations...")
                from flask_migrate import upgrade
                upgrade()
                logger.info("Database migrations applied successfully")
            except Exception as migration_error:
                logger.warning(f"Migration warning: {str(migration_error)}")
                logger.warning("Continuing without migrations...")
            
            logger.info("Application initialization completed")
            return app

    except Exception as e:
        logger.error(f"Error during app creation: {str(e)}")
        logger.exception("Full stack trace:")
        raise

@login_manager.user_loader
def load_user(user_id):
    from models import User
    try:
        return User.query.get(int(user_id))
    except Exception as e:
        logger.error(f"Error loading user {user_id}: {str(e)}")
        return None

# Initialize the application (only if running directly)
if __name__ == '__main__':
    app = create_app()
