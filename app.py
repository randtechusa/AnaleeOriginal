import os
import logging
import sys
from datetime import datetime
import time
from flask import Flask, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from dotenv import load_dotenv
from sqlalchemy import text, create_engine
from flask_apscheduler import APScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from utils.backup_manager import DatabaseBackupManager, init_backup_scheduler

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
        
        # Configure Flask application with improved error handling
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            logger.error("DATABASE_URL environment variable is not set")
            raise ValueError("DATABASE_URL environment variable is not set")

        # Handle legacy database URLs and ensure proper format with validation
        try:
            if database_url.startswith("postgres://"):
                database_url = database_url.replace("postgres://", "postgresql://", 1)
            
            # Validate database URL format
            if not any(database_url.startswith(prefix) for prefix in ['postgresql://', 'postgresql+psycopg2://']):
                if '@' in database_url and ':' in database_url:
                    database_url = f"postgresql://{database_url}"
                else:
                    raise ValueError("Invalid database URL format")
            
            logger.info("Database URL validated successfully")
            
            # Test database connection
            from sqlalchemy import create_engine
            engine = create_engine(database_url)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                logger.info("Database connection test successful")
                
        except Exception as e:
            logger.error(f"Database configuration error: {str(e)}")
            raise

        
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
        
        # Initialize and start scheduler with improved rate limit handling
        try:
            # Configure rate limiting with exponential backoff
            # Configure rate limiting with improved stability
            app.config.update({
                'RATELIMIT_DEFAULT': "100 per minute",
                'RATELIMIT_STORAGE_URL': database_url,
                'RATELIMIT_STRATEGY': 'fixed-window',
                'RATELIMIT_STORAGE_OPTIONS': {'connection_pool': True},
                'RATELIMIT_KEY_PREFIX': 'global_',
                'RATELIMIT_HEADERS_ENABLED': True,
                'SCHEDULER_EXECUTORS': {'default': {'type': 'threadpool', 'max_workers': 20}},
                'SCHEDULER_JOB_DEFAULTS': {'coalesce': False, 'max_instances': 3}
            })
            
            app.config.from_object(Config)
            scheduler.init_app(app)
            if not scheduler.running:
                scheduler.start()
                logger.debug("Scheduler started successfully")
            else:
                logger.debug("Scheduler already running")
            logger.info("Flask extensions, scheduler, and rate limiting initialized successfully")
        except Exception as scheduler_error:
            logger.error(f"Error initializing scheduler: {str(scheduler_error)}")
            logger.warning("Application will continue without background task scheduling")

        with app.app_context():
            try:
                # Import models here to avoid circular imports
                from models import User, Account, Transaction, UploadedFile, CompanySettings
                logger.debug("Models imported")

                # Initialize test suite with proper error handling and database verification
                try:
                    # Verify database connection before initializing test suite
                    db.session.execute(text('SELECT 1'))
                    db.session.commit()
                    
                    # Import test suite after confirming database connection
                    try:
                        from tests.rollback_verification import RollbackVerificationTest
                        if not hasattr(app, 'rollback_verification'):
                            logger.info("Initializing rollback verification test suite...")
                            app.rollback_verification = RollbackVerificationTest(app)
                            
                            # Initialize test suite without immediate verification
                            logger.info("Rollback verification test suite initialized")
                            
                            # Schedule verification for after app startup
                            @app.before_first_request
                            def verify_test_suite():
                                try:
                                    reference_time = datetime.utcnow()
                                    verification_result = app.rollback_verification.verify_transaction_consistency(reference_time)
                                    if verification_result:
                                        logger.info("Rollback verification test suite verified successfully")
                                    else:
                                        logger.warning("Rollback verification test suite verification failed")
                                except Exception as verify_error:
                                    logger.error(f"Error during test suite verification: {str(verify_error)}")
                        else:
                            logger.info("Rollback verification test suite already initialized")
                    except ImportError as import_error:
                        logger.error(f"Could not import rollback verification test suite: {str(import_error)}")
                        logger.warning("Application will continue without rollback verification capability")
                except Exception as test_suite_error:
                    logger.error(f"Error setting up rollback verification: {str(test_suite_error)}")
                    if current_app.debug:
                        logger.exception("Full traceback for test suite setup error:")

                # Test database connection with improved retry mechanism
                max_retries = 3
                retry_delay = 2
                
                for attempt in range(max_retries):
                    try:
                        logger.info(f"Testing database connection (attempt {attempt + 1}/{max_retries})...")
                        result = db.session.execute(text('SELECT current_database(), current_user, version()'))
                        connection_info = result.fetchone()
                        logger.info(f"Connected to database: {connection_info[0]} as user: {connection_info[1]}")
                        logger.info(f"Database version: {connection_info[2]}")
                        logger.debug("Database connection test successful")
                        break
                    except Exception as db_error:
                        logger.error(f"Database connection attempt {attempt + 1} failed: {str(db_error)}")
                        if attempt < max_retries - 1:
                            logger.info(f"Retrying in {retry_delay} seconds...")
                            time.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                        else:
                            logger.error("All database connection attempts failed:", exc_info=True)
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