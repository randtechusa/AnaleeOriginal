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
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(24).hex()

    # Database configuration with enhanced connection handling
    # Try to use PostgreSQL connection from environment variables first
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    
    def init_sqlite():
        sqlite_path = os.path.join(os.getcwd(), 'instance', 'dev.db')
        os.makedirs('instance', exist_ok=True)
        return f'sqlite:///{sqlite_path}'

    def test_db_connection(uri):
        from sqlalchemy import create_engine, text
        try:
            if isinstance(uri, str) and uri.startswith('postgres://'):
                uri = uri.replace('postgres://', 'postgresql://')
                
            # Create engine with appropriate parameters for the database type
            if isinstance(uri, str) and 'postgresql://' in uri:
                # PostgreSQL connections
                engine = create_engine(uri, pool_pre_ping=True)
            else:
                # SQLite or other connections
                engine = create_engine(uri, pool_pre_ping=True)
            with engine.connect() as conn:
                conn.execute(text('SELECT 1'))
            return True, uri
        except Exception as e:
            print(f"Database connection failed: {e}")
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
            
    # Define SQLAlchemy engine options directly as a dictionary instead of as a property
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
    config_class = None
    config_classes = {
        'development': DevelopmentConfig,
        'production': ProductionConfig,
        'testing': TestingConfig,
        'default': DevelopmentConfig
    }
    
    config_class = config_classes.get(config_name, DevelopmentConfig)
    
    # Conditionally add PostgreSQL-specific connection args if we're using PostgreSQL
    # This ensures SQLite connections don't get incompatible options
    if hasattr(config_class, 'SQLALCHEMY_DATABASE_URI') and 'postgresql' in config_class.SQLALCHEMY_DATABASE_URI:
        if not hasattr(config_class, 'SQLALCHEMY_ENGINE_OPTIONS'):
            config_class.SQLALCHEMY_ENGINE_OPTIONS = {}
        
        # Add PostgreSQL-specific connection args
        if 'connect_args' not in config_class.SQLALCHEMY_ENGINE_OPTIONS:
            config_class.SQLALCHEMY_ENGINE_OPTIONS['connect_args'] = {}
            
        config_class.SQLALCHEMY_ENGINE_OPTIONS['connect_args'].update({
            'connect_timeout': 10,
            'application_name': 'icountant'
        })
        
    return config_class