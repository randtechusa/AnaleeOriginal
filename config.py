import os
import time
import logging
from datetime import timedelta
from sqlalchemy import create_engine, text

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Config:
    """Base configuration"""
    # Use a fixed secret key for development (more consistent for debugging)
    # In production, always set SECRET_KEY in environment variables
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-for-icountant-platform'

    # Database configuration with enhanced connection handling
    # Try to use PostgreSQL connection from environment variables first
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')

    def init_sqlite():
        sqlite_path = os.path.join(os.getcwd(), 'instance', 'dev.db')
        os.makedirs('instance', exist_ok=True)
        return f'sqlite:///{sqlite_path}'

    def test_db_connection(uri):
        from sqlalchemy import create_engine, text
        from sqlalchemy.exc import OperationalError
        
        logger.info(f"Testing database connection to: {uri}")
        
        try:
            if isinstance(uri, str) and uri.startswith('postgres://'):
                uri = uri.replace('postgres://', 'postgresql://')
                logger.info("Converted postgres:// to postgresql:// for compatibility")

            # Determine the database type for specialized handling
            is_sqlite = 'sqlite://' in uri.lower() if isinstance(uri, str) else False
            is_postgresql = 'postgresql://' in uri.lower() if isinstance(uri, str) else False
            is_neon = 'neon.tech' in uri.lower() if isinstance(uri, str) else False
            
            # Log the database type for better diagnostics
            if is_sqlite:
                logger.info("Detected SQLite database")
            elif is_neon:
                logger.info("Detected Neon PostgreSQL database")
            elif is_postgresql:
                logger.info("Detected PostgreSQL database")
            else:
                logger.info(f"Unknown database type: {uri}")
                
            # Create engine with appropriate parameters for the database type
            engine_opts = {'pool_pre_ping': True}
            
            if is_postgresql:
                # PostgreSQL connections with better timeout settings
                engine_opts.update({
                    'pool_size': 5,
                    'max_overflow': 10,
                    'pool_timeout': 30,
                    'pool_recycle': 1800,
                    'connect_args': {'connect_timeout': 10}
                })
            
            engine = create_engine(uri, **engine_opts)
            
            # Test the connection
            with engine.connect() as conn:
                conn.execute(text('SELECT 1'))
                
            logger.info("Database connection test successful")
            return True, uri
            
        except OperationalError as e:
            error_str = str(e).lower()
            if 'endpoint is disabled' in error_str:
                logger.warning("PostgreSQL endpoint is disabled. This is normal for serverless databases after periods of inactivity.")
                # Provide more detailed error message
                error_msg = "PostgreSQL endpoint is disabled and needs to be woken up. This is normal for serverless databases."
            else:
                error_msg = f"Database connection failed: {e}"
                logger.error(error_msg)
                
            return False, None
            
        except Exception as e:
            error_msg = f"Unexpected error during database connection test: {e}"
            logger.error(error_msg)
            logger.error(f"Error type: {type(e).__name__}")
            return False, None

    # Try to use PostgreSQL first, fallback to SQLite if unavailable
    if not SQLALCHEMY_DATABASE_URI:
        SQLALCHEMY_DATABASE_URI = init_sqlite()
        logger.info("No DATABASE_URL found, using SQLite for development")
    else:
        # Convert postgres:// to postgresql:// if needed (for compatibility)
        if SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
            SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://')
            logger.info("Converted postgres:// to postgresql:// in connection string")

        # Test PostgreSQL connection
        success, tested_uri = test_db_connection(SQLALCHEMY_DATABASE_URI)
        if success:
            logger.info("Successfully connected to PostgreSQL database")
        else:
            logger.warning("PostgreSQL connection failed - endpoint may be disabled. Using SQLite fallback.")
            SQLALCHEMY_DATABASE_URI = init_sqlite()

        logger.info(f"Using database: {'PostgreSQL' if success else 'SQLite (fallback)'}")

    # Ensure SQLite directory exists
    if 'sqlite' in SQLALCHEMY_DATABASE_URI:
        os.makedirs('instance', exist_ok=True)

    # Define SQLAlchemy engine options directly as a class attribute (not a property)
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 5,             # Keep 5 connections ready
        'max_overflow': 10,         # Allow up to 10 more during spikes
        'pool_timeout': 30,         # Wait up to 30 sec for connection
        'pool_recycle': 1800,       # Recycle connections every 30 min
        'pool_pre_ping': True       # Verify connections before using
    }

    # SQLite doesn't support all PostgreSQL connection arguments
    # These will be added conditionally in the Config initialization if needed

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=60)
    SESSION_TYPE = 'filesystem'

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False

def get_config(config_name='development'):
    """Get configuration class based on environment"""
    config_classes = {
        'development': DevelopmentConfig,
        'production': ProductionConfig,
        'testing': TestingConfig,
        'default': DevelopmentConfig
    }

    config_class = config_classes.get(config_name, DevelopmentConfig)

    # Create a new instance to avoid modifying the class itself
    config_instance = config_class()

    # Conditionally add PostgreSQL-specific connection args if we're using PostgreSQL
    # This ensures SQLite connections don't get incompatible options
    db_uri = getattr(config_instance, 'SQLALCHEMY_DATABASE_URI', '')
    if db_uri and isinstance(db_uri, str) and 'postgresql' in db_uri:
        if not hasattr(config_instance, 'SQLALCHEMY_ENGINE_OPTIONS'):
            config_instance.SQLALCHEMY_ENGINE_OPTIONS = {}

        # Add PostgreSQL-specific connection args
        engine_options = config_instance.SQLALCHEMY_ENGINE_OPTIONS
        if 'connect_args' not in engine_options:
            engine_options['connect_args'] = {}

        engine_options['connect_args'].update({
            'connect_timeout': 10,
            'application_name': 'icountant'
        })

    return config_instance