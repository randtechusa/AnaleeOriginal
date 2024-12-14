import os
import logging
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from dotenv import load_dotenv
from sqlalchemy import text
from flask_apscheduler import APScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from utils.backup_manager import DatabaseBackupManager, init_backup_scheduler # Added import for backup manager

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
scheduler = APScheduler()

# Configure APScheduler
class Config:
    SCHEDULER_API_ENABLED = True
    SCHEDULER_EXECUTORS = {
        'default': {'type': 'threadpool', 'max_workers': 20}
    }
    SCHEDULER_JOB_DEFAULTS = {
        'coalesce': False,
        'max_instances': 3
    }

def create_app():
    """Create and configure the Flask application"""
    try:
        # Create Flask app
        app = Flask(__name__)
        logger.info("Starting Flask application initialization...")
        
        # Configure Flask application
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            logger.error("DATABASE_URL environment variable is not set")
            raise ValueError("DATABASE_URL environment variable is not set")

        # Handle legacy database URLs and ensure proper format
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        elif not database_url.startswith("postgresql://"):
            database_url = f"postgresql://{database_url}"
            
        logger.info("Database URL configured successfully")
        
        # Configure Flask app
        app.config.update(
            SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", os.urandom(24).hex()),
            SQLALCHEMY_DATABASE_URI=database_url,
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TEMPLATES_AUTO_RELOAD=True,
            DEBUG=True
        )
        logger.debug("Flask app configuration completed")

        # Initialize Flask extensions
        db.init_app(app)
        migrate.init_app(app, db)
        login_manager.init_app(app)
        login_manager.login_view = 'main.login'
        
        # Initialize and start scheduler
        try:
            app.config.from_object(Config)
            scheduler.init_app(app)
            if not scheduler.running:
                scheduler.start()
                logger.debug("Scheduler started successfully")
            else:
                logger.debug("Scheduler already running")
            logger.debug("Flask extensions and scheduler initialized successfully")
        except Exception as scheduler_error:
            logger.error(f"Error initializing scheduler: {str(scheduler_error)}")
            logger.warning("Application will continue without background task scheduling")

        with app.app_context():
            try:
                # Import models here to avoid circular imports
                from models import User, Account, Transaction, UploadedFile, CompanySettings
                logger.debug("Models imported")

                # Test database connection first
                try:
                    # Test database connection with detailed error logging
                    logger.info("Testing database connection...")
                    result = db.session.execute(text('SELECT current_database(), current_user, version()'))
                    connection_info = result.fetchone()
                    logger.info(f"Connected to database: {connection_info[0]} as user: {connection_info[1]}")
                    logger.info(f"Database version: {connection_info[2]}")
                    logger.debug("Database connection test successful")
                except Exception as db_error:
                    logger.error(f"Database connection test failed: {str(db_error)}")
                    logger.error("Full error details:", exc_info=True)
                    raise

                # Register blueprints first
                try:
                    from routes import main as main_blueprint
                    app.register_blueprint(main_blueprint)
                    logger.debug("Blueprints registered successfully")
                except Exception as blueprint_error:
                    logger.error(f"Error registering blueprints: {str(blueprint_error)}")
                    raise

                # Initialize database tables
                try:
                    db.create_all()
                    logger.debug("Database tables created successfully")
                except Exception as db_error:
                    logger.error(f"Error creating database tables: {str(db_error)}")
                    raise

                # Initialize backup manager last (non-critical)
                try:
                    backup_manager = DatabaseBackupManager(app.config['SQLALCHEMY_DATABASE_URI'])
                    logger.info("Backup manager initialized successfully")
                    
                    # Initialize backup system
                    backup_scheduler = init_backup_scheduler(app)
                    logger.info("Database backup system initialized successfully")
                except Exception as backup_error:
                    logger.error(f"Error in backup system: {str(backup_error)}")
                    logger.warning("Application will continue without backup functionality")
                
                logger.info("Application initialization completed successfully")
                return app
                
            except Exception as context_error:
                logger.error(f"Error in application context: {str(context_error)}")
                raise

    except Exception as e:
        logger.error(f"Error during app creation: {str(e)}")
        logger.exception("Full stack trace:")
        raise