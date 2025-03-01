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
            
    # Configure SQLAlchemy pool settings
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 5,
        'pool_timeout': 30,
        'pool_recycle': 1800,
        'pool_pre_ping': True
    }

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
    return config_classes.get(config_name, DevelopmentConfig)