import os
import logging
import sys
from datetime import datetime
from flask import Flask, current_app
from flask_migrate import Migrate
from dotenv import load_dotenv
from sqlalchemy import text
from flask_apscheduler import APScheduler
from models import db, login_manager

# Configure logging with more detailed error reporting
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log')
    ]
)

# Enable SQLAlchemy detailed logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.DEBUG)
logging.getLogger('sqlalchemy.pool').setLevel(logging.DEBUG)

# Create module logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# Load environment variables
load_dotenv()


# Initialize Flask extensions
migrate = Migrate()
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

def verify_database():
    """Verify database connection and check required tables"""
    try:
        logger.info("Verifying database connection...")
        with db.engine.connect() as conn:
            # Test basic connection
            conn.execute(text('SELECT 1'))
            logger.info("Basic database connection successful")
            
            # List existing tables
            tables_query = text("""
                SELECT tablename 
                FROM pg_catalog.pg_tables 
                WHERE schemaname != 'pg_catalog' 
                AND schemaname != 'information_schema';
            """)
            existing_tables = [row[0] for row in conn.execute(tables_query)]
            logger.info(f"Existing tables: {existing_tables}")
            
            # Create tables if they don't exist
            try:
                db.create_all()
                logger.info("Database tables created/verified successfully")
                
                # Verify each model's table exists
                for table in db.metadata.tables:
                    if table not in existing_tables:
                        logger.warning(f"Table {table} may not have been created properly")
                    else:
                        logger.info(f"Table {table} verified")
                return True
                
            except Exception as table_error:
                logger.error(f"Error creating tables: {str(table_error)}")
                logger.exception("Full table creation error stacktrace:")
                return False
            
    except Exception as db_error:
        logger.error(f"Database connection failed: {str(db_error)}")
        logger.exception("Full database connection error stacktrace:")
        return False

def create_app(env=os.environ.get('FLASK_ENV', 'production')):
    """Create and configure the Flask application"""
    try:
        # Initialize Flask application
        app = Flask(__name__)
        
        # Strict environment handling
        if env not in ['development', 'production', 'testing']:
            env = 'production'
            logger.warning("Invalid environment specified, defaulting to production for safety")
        elif env == 'development' and os.environ.get('FLASK_ENV') != 'development':
            env = 'production'
            logger.warning("Development mode blocked in non-development environment")
        
        logger.info(f"Starting Flask application initialization in {env} environment...")
        
        # Load the appropriate configuration
        app.config.from_object(f'config.{env.capitalize()}Config')
        
        # Get appropriate database URL based on environment
        if env == 'development':
            database_url = os.environ.get("DEV_DATABASE_URL", os.environ.get("DATABASE_URL"))
            logger.info("Using development database configuration")
        else:
            database_url = os.environ.get("DATABASE_URL")
            
        if not database_url:
            logger.error("Database URL is not set for the current environment")
            return None
            
        # Handle legacy database URL format
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
            logger.info("Converted legacy postgres:// URL format to postgresql://")

        # Handle legacy database URL format
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
            logger.info("Converted legacy postgres:// URL format to postgresql://")
            
        # Verify database URL format
        if not database_url.startswith(('postgresql://', 'postgres://')):
            logger.error("Invalid database URL format")
            return None
            
        # Configure logging for database operations with proper level
        db_logger = logging.getLogger('sqlalchemy.engine')
        db_logger.setLevel(logging.INFO)
        
        # Verify database URL format
        if not any(database_url.startswith(prefix) for prefix in ['postgresql://', 'postgres://']):
            logger.error(f"Invalid database URL format")
            return None
            
        # Basic application configuration check
        if not app.config:
            logger.error("Flask app configuration missing")
            return None
            
        # Configure Flask app with essential settings and enhanced database configuration
        config = {
            'SECRET_KEY': os.environ.get("FLASK_SECRET_KEY", os.urandom(24).hex()),
            'SQLALCHEMY_DATABASE_URI': database_url,
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
            'TEMPLATES_AUTO_RELOAD': True,
            'SQLALCHEMY_ENGINE_OPTIONS': {
                'pool_pre_ping': True,
                'pool_size': 5,  # Reduced pool size for better stability
                'pool_timeout': 30,  # Reduced timeout
                'pool_recycle': 300,  # 5 minutes recycle
                'max_overflow': 2,  # Reduced max overflow
                'echo': True if env == 'testing' else False,
                'echo_pool': 'debug' if env == 'testing' else False,
                'connect_args': {
                    'connect_timeout': 5,  # Reduced connect timeout
                    'application_name': 'flask_app',
                    'keepalives': 1,
                    'keepalives_idle': 30,
                    'keepalives_interval': 10,
                    'keepalives_count': 5,
                    'client_encoding': 'utf8',
                    'options': '-c timezone=utc'
                }
            }
        }
    
    # Environment-specific configuration
        if env == 'testing':
            config.update({
                'TESTING': True,
                'DEBUG': True,
                'ENABLE_ROLLBACK_TESTS': True,
                'SQLALCHEMY_DATABASE_URI': os.environ.get('TEST_DATABASE_URL', f"{database_url}_test"),
                'RATELIMIT_STORAGE_URL': os.environ.get('TEST_DATABASE_URL', f"{database_url}_test")
            })
        else:
            config.update({
                'TESTING': False,
                'DEBUG': False,
                'ENABLE_ROLLBACK_TESTS': False,
                'SQLALCHEMY_DATABASE_URI': database_url,
                'RATELIMIT_STORAGE_URL': database_url
            })
        
        app.config.update(config)
        logger.debug("Flask app configuration completed")

        # Initialize Flask extensions with enhanced error handling
        try:
            db.init_app(app)
            migrate.init_app(app, db, directory='migrations')
            login_manager.init_app(app)
            login_manager.login_view = 'main.login'
            logger.info("Flask extensions initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Flask extensions: {str(e)}")
            raise
        
        # Import user loader here to avoid circular imports
        from models import load_user
        login_manager.user_loader(load_user)
        
        # Initialize scheduler
        scheduler.init_app(app)
        if not scheduler.running:
            scheduler.start()
            logger.debug("Scheduler started successfully")
        
        with app.app_context():
            try:
                # Verify database connection with timeout
                try:
                    db.session.execute(text('SELECT 1'))
                    logger.info("Database connection verified")
                except Exception as db_error:
                    logger.error(f"Database connection failed: {str(db_error)}")
                    return None
                
                # Import models with error handling
                try:
                    from models import User, Account, Transaction, UploadedFile, CompanySettings
                    logger.debug("Models imported successfully")
                except ImportError as import_error:
                    logger.error(f"Failed to import models: {str(import_error)}")
                    return None
                
                # Create database tables with proper error handling
                try:
                    db.create_all()
                    logger.info("Database tables created successfully")
                except Exception as table_error:
                    logger.error(f"Failed to create database tables: {str(table_error)}")
                    return None
                
                # Initialize test suite (non-critical)
                try:
                    from tests.rollback_verification import RollbackVerificationTest
                    if not hasattr(app, 'rollback_verification'):
                        app.rollback_verification = RollbackVerificationTest(app)
                        logger.info("Rollback verification test suite initialized")
                except ImportError as e:
                    logger.warning(f"Test suite module not found (non-critical): {str(e)}")
                except Exception as e:
                    logger.warning(f"Test suite initialization deferred (non-critical): {str(e)}")
                
                # Register blueprints
                try:
                    from routes import main as main_blueprint
                    from reports import reports as reports_blueprint
                    
                    app.register_blueprint(main_blueprint)
                    app.register_blueprint(reports_blueprint)
                    logger.debug("Blueprints registered successfully")
                except Exception as blueprint_error:
                    logger.error(f"Error registering blueprints: {str(blueprint_error)}")
                    raise
                
                logger.info("Application initialization completed successfully")
                return app
                
            except Exception as e:
                logger.error(f"Error during application initialization: {str(e)}")
                raise
                
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
        port = 5000  # Force port 5000 for Replit
        logger.info(f"Configuring server to run on port {port}")
        
        # Verify database connection before starting
        with app.app_context():
            if not verify_database():
                logger.error("Database verification failed")
                sys.exit(1)
                
            # Ensure all tables exist
            try:
                db.create_all()
                logger.info("Database tables verified/created")
            except Exception as db_error:
                logger.error(f"Error creating database tables: {str(db_error)}")
                sys.exit(1)
            
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