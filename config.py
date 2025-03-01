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
    # Original database URI - temporarily commented out due to connection issues
    # SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    
    def init_sqlite():
        sqlite_path = os.path.join(os.getcwd(), 'instance', 'dev.db')
        os.makedirs('instance', exist_ok=True)
        return f'sqlite:///{sqlite_path}'

    def test_db_connection(uri):
        from sqlalchemy import create_engine, text
        try:
            if isinstance(uri, str) and uri.startswith('postgres://'):
                uri = uri.replace('postgres://', 'postgresql://')
                
            # Use connect_timeout only for PostgreSQL connections
            connect_args = {}
            if isinstance(uri, str) and 'postgresql://' in uri:
                connect_args = {'connect_timeout': 10}
                
            engine = create_engine(uri, pool_pre_ping=True, connect_args=connect_args)
            with engine.connect() as conn:
                conn.execute(text('SELECT 1'))
            return True, uri
        except Exception as e:
            print(f"Database connection failed: {e}")
            return False, None

    # Force use SQLite for development until PostgreSQL issue is resolved
    SQLALCHEMY_DATABASE_URI = init_sqlite()
    logger.info("Using SQLite for development (PostgreSQL temporarily disabled)")
    
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