import os
import logging
import sys
from datetime import datetime
from flask import Flask, current_app
from flask_migrate import Migrate
from dotenv import load_dotenv
from sqlalchemy import text
from flask_apscheduler import APScheduler
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()

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
    """Verify database connection and protect data integrity"""
    try:
        logger.info("Verifying database connection and protection mechanisms...")
        with db.engine.connect() as conn:
            # Test basic connection with timeout
            try:
                result = conn.execute(text('SELECT 1'))
                if not result:
                    logger.error("Database connection test failed")
                    return False
                logger.info("Basic database connection successful")
            except Exception as conn_error:
                logger.error(f"Database connection failed: {str(conn_error)}")
                return False

            # List and verify existing tables with proper error handling
            try:
                tables_query = text("""
                    SELECT tablename 
                    FROM pg_catalog.pg_tables 
                    WHERE schemaname != 'pg_catalog' 
                    AND schemaname != 'information_schema';
                """)
                existing_tables = [row[0] for row in conn.execute(tables_query)]
                logger.info(f"Existing tables: {existing_tables}")
            except Exception as table_error:
                logger.error(f"Error querying tables: {str(table_error)}")
                return False
            
            # Verify environment separation - Consolidated check
            if current_app.config.get('ENV') == 'production':
                logger.info("Production environment detected - enabling strict protections")
                required_settings = [
                    'PROTECT_PRODUCTION',
                    'PROTECT_DATA',
                    'PROTECT_CHART_OF_ACCOUNTS',
                    'PROTECT_COMPLETED_FEATURES'
                ]
                if not all(current_app.config.get(setting) for setting in required_settings):
                    logger.error("Production protection mechanisms not fully enabled")
                    return False
            
            # Create/verify tables with protection
            try:
                # Protect chart of accounts if it exists
                if 'account' in existing_tables:
                    logger.info("Chart of accounts found - enabling protection")
                    if not current_app.config.get('PROTECT_CHART_OF_ACCOUNTS'):
                        logger.error("Chart of accounts protection not enabled")
                        return False
                
                # Create missing tables only in development with protection
                try:
                    if current_app.config.get('ENV') != 'production':
                        db.create_all()
                        logger.info("Database tables verified in development environment")
                    
                    # Verify critical tables with enhanced protection
                    protected_tables = current_app.config.get('PROTECTED_TABLES', ['account'])
                    for table in protected_tables:
                        if table not in existing_tables:
                            logger.error(f"Protected table {table} missing")
                            return False
                        logger.info(f"Protected table {table} verified")
                    
                    return True
                    
                except Exception as table_error:
                    logger.error(f"Error verifying tables: {str(table_error)}")
                    logger.exception("Full table verification error stacktrace:")
                    return False
            except Exception as create_error:
                logger.error(f"Error creating or verifying tables: {str(create_error)}")
                logger.exception("Full table creation/verification error stacktrace:")
                return False
            
    except Exception as db_error:
        logger.error(f"Database verification failed: {str(db_error)}")
        logger.exception("Full database verification error stacktrace:")
        return False

def create_app(env=None):
    """Create and configure the Flask application with strict environment protection"""
    try:
        # Initialize Flask application with enhanced protection
        app = Flask(__name__)
        
        # Configure logging for production
        if not app.debug:
            file_handler = logging.FileHandler('app.log')
            file_handler.setLevel(logging.INFO)
            app.logger.addHandler(file_handler)
            
        # Get and validate environment with strict protection
        if env is None:
            env = os.environ.get('FLASK_ENV', '').lower()
            if not env:
                logger.warning("FLASK_ENV not set, defaulting to development for safety")
                env = 'development'
            
        # Strict environment validation and protection
        if env not in ['development', 'production', 'testing']:
            logger.warning(f"Invalid environment '{env}' specified, defaulting to development")
            env = 'development'
        
        logger.info(f"Starting Flask application initialization in {env} environment with protection mechanisms...")
            
        # Enhanced environment separation checks for production
        if env == 'production':
            # Required protection variables
            required_vars = [
                'PROTECT_PRODUCTION',
                'PROTECT_DATA',
                'PROTECT_CHART_OF_ACCOUNTS'
            ]
            missing_vars = [var for var in required_vars if not os.environ.get(var)]
            if missing_vars:
                logger.error(f"Missing required production protection variables: {missing_vars}")
                return None
                
            # Verify development features are disabled
            if os.environ.get('DEVELOPMENT_FEATURES_ENABLED', '').lower() == 'true':
                logger.error("Development features must be disabled in production")
                return None
            
            logger.info("Production mode activated with full protection")
        
        # Environment separation protection - Consolidated check
        if env == 'production':
            if os.environ.get('DEVELOPMENT_FEATURES_ENABLED', '').lower() == 'true':
                logger.error("Development features cannot be enabled in production")
                return None
            logger.info("Production mode activated with full protection")
            
        logger.info(f"Starting Flask application initialization in {env} environment with protection mechanisms...")
        
        # Load the appropriate configuration
        app.config.from_object(f'config.{env.capitalize()}Config')
        
        # Get and validate database URL with strict environment separation
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            logger.error("Database URL is not set for the current environment")
            return None
            
        # Handle legacy database URL format and ensure proper format
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
            logger.info("Converted legacy postgres:// URL format to postgresql://")
        elif not database_url.startswith("postgresql://"):
            database_url = f"postgresql://{database_url}"
            logger.info("Added postgresql:// prefix to database URL")
            
        # Verify database URL format
        if not database_url.startswith('postgresql://'):
            logger.error("Invalid database URL format")
            return None
            
        # Enhanced environment separation verification
        if env == 'production':
            dev_database_url = os.environ.get('DEV_DATABASE_URL')
            if dev_database_url and dev_database_url == database_url:
                logger.error("Critical: Development and production databases cannot be the same")
                return None
            logger.info("Environment separation verified for production")
        
        # Configure logging for database operations with proper level
        db_logger = logging.getLogger('sqlalchemy.engine')
        db_logger.setLevel(logging.INFO)
        
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
                    if env != 'production':
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
                
                # Register blueprints with enhanced protection
                try:
                    # Import and register blueprints only if environment checks pass
                    if verify_database():
                        try:
                            # Set environment protection flags
                            app.config['PROTECT_DATA'] = os.environ.get('PROTECT_DATA', 'true').lower() == 'true'
                            app.config['PROTECT_CHART_OF_ACCOUNTS'] = os.environ.get('PROTECT_CHART_OF_ACCOUNTS', 'true').lower() == 'true'
                            app.config['PROTECT_COMPLETED_FEATURES'] = os.environ.get('PROTECT_COMPLETED_FEATURES', 'true').lower() == 'true'
                            
                            # Import blueprints with proper error handling
                            try:
                                # Import main blueprint first
                                from routes import main as main_blueprint
                                logger.info("Main blueprint imported successfully")
                                
                                # Import rules blueprint with enhanced protection
                                try:
                                    from routes.rules import rules as rules_blueprint
                                    
                                    # Verify required protection attributes
                                    required_attrs = ['protected_routes']
                                    if not all(hasattr(rules_blueprint, attr) for attr in required_attrs):
                                        logger.error("Rules blueprint missing required protection attributes")
                                        if env == 'production':
                                            return None
                                    else:
                                        logger.info("Rules blueprint protection verified")
                                    
                                    # Initialize routes before registration
                                    if hasattr(rules_blueprint, 'init_routes'):
                                        try:
                                            rules_blueprint.init_routes()
                                            logger.info("Rules blueprint routes initialized successfully")
                                        except Exception as init_error:
                                            logger.error(f"Failed to initialize rules routes: {str(init_error)}")
                                            if env == 'production':
                                                return None
                                    
                                    logger.info("Rules blueprint imported and initialized successfully")
                                except ImportError as rules_error:
                                    logger.error(f"Failed to import rules blueprint: {str(rules_error)}")
                                    if env == 'production':
                                        return None
                                    rules_blueprint = None
                                except Exception as e:
                                    logger.error(f"Unexpected error importing rules blueprint: {str(e)}")
                                    if env == 'production':
                                        return None
                                    rules_blueprint = None
                            except ImportError as main_error:
                                logger.error(f"Failed to import main blueprint: {str(main_error)}")
                                return None
                            except Exception as e:
                                logger.error(f"Unexpected error importing main blueprint: {str(e)}")
                                return None

                            # Additional protection for production routes
                            if env == 'production':
                                required_protections = ['protected_routes']
                                if not hasattr(main_blueprint, 'protected_routes'):
                                    logger.error("Main blueprint missing production protection")
                                    return None
                                if rules_blueprint and not hasattr(rules_blueprint, 'protected_routes'):
                                    logger.error("Rules blueprint missing production protection")
                                    return None
                            
                            # Register blueprints with enhanced protection
                            try:
                                # Register main blueprint first
                                app.register_blueprint(main_blueprint)
                                logger.info("Main blueprint registered successfully")
                                
                                # Register rules blueprint with environment checks
                                if rules_blueprint:
                                    # Verify environment protection
                                    if env == 'production':
                                        if not all(hasattr(rules_blueprint, attr) for attr in ['protected_routes']):
                                            logger.error("Rules blueprint missing production protection")
                                            return None
                                    
                                    # Register with proper error handling
                                    app.register_blueprint(rules_blueprint)
                                    logger.info("Rules blueprint registered successfully")
                                    
                                    # Initialize the blueprint routes
                                    if hasattr(rules_blueprint, 'init_blueprint'):
                                        rules_blueprint.init_blueprint(rules_blueprint)
                                        logger.info("Rules blueprint routes initialized successfully")
                                
                                logger.info("All blueprints registered successfully with protection")
                            except Exception as blueprint_error:
                                logger.error(f"Error registering blueprints: {str(blueprint_error)}")
                                if env == 'production':
                                    return None
                                raise
                            
                            logger.info("All blueprints registered successfully with protection")
                        except Exception as blueprint_error:
                            logger.error(f"Error registering blueprints: {str(blueprint_error)}")
                            if env == 'production':
                                return None
                            raise
                    else:
                        logger.error("Database verification failed, cannot register blueprints")
                        return None
                except ImportError as import_error:
                    logger.error(f"Critical: Blueprint import failed: {str(import_error)}")
                    return None
                except Exception as blueprint_error:
                    logger.error(f"Critical: Blueprint registration failed: {str(blueprint_error)}")
                    return None
                
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
                if app.config.get('ENV') != 'production':
                    db.create_all()
                    logger.info("Database tables verified/created")
            except Exception as db_error:
                logger.error(f"Error creating database tables: {str(db_error)}")
                sys.exit(1)
            
        # Start the server with proper protection
        logger.info(f"Starting Flask application on http://0.0.0.0:{port}")
        if app.config.get('ENV') == 'production':
            app.run(
                host='0.0.0.0',
                port=port,
                debug=False,
                use_reloader=False
            )
        else:
            app.run(
                host='0.0.0.0',
                port=port,
                debug=True,
                use_reloader=False  # Disable reloader to prevent duplicate processes
            )
    except Exception as e:
        logger.error(f"Critical error starting application: {str(e)}")
        logger.exception("Full stack trace:")
        sys.exit(1)