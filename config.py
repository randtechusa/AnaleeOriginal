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
            
    # Configure SQLAlchemy pool settings based on database type
    @property
    def SQLALCHEMY_ENGINE_OPTIONS(self):
        """
        Dynamic connection pool settings based on database type
        
        For PostgreSQL (especially serverless like Neon), we use smaller initial pool
        with ability to overflow temporarily during traffic spikes.
        
        For SQLite, we use minimal pooling since it's file-based.
        """
        if hasattr(self, '_engine_options'):
            return self._engine_options
            
        uri = self.SQLALCHEMY_DATABASE_URI
        
        if 'sqlite' in uri.lower():
            # SQLite needs minimal pooling
            self._engine_options = {
                'pool_size': 1,
                'max_overflow': 2,
                'pool_timeout': 20,
                'pool_recycle': 3600,
                'pool_pre_ping': True,
            }
        else:
            # PostgreSQL settings - optimized for serverless
            self._engine_options = {
                'pool_size': 5,             # Keep 5 connections ready
                'max_overflow': 10,         # Allow up to 10 more during spikes
                'pool_timeout': 30,         # Wait up to 30 sec for connection
                'pool_recycle': 1800,       # Recycle connections every 30 min
                'pool_pre_ping': True,      # Verify connections before using
                'connect_args': {
                    'connect_timeout': 10,  # Connect timeout in seconds
                    'application_name': 'icountant'  # Help identify app in db logs
                }
            }
            
            # If this is a Neon database, try to use their connection pooler
            if 'neon.tech' in uri.lower():
                # Convert to use Neon's connection pooling if not already
                if '-pooler.' not in uri.lower():
                    uri_parts = uri.split('.')
                    # Format: region.aws.neon.tech -> region-pooler.aws.neon.tech
                    for i, part in enumerate(uri_parts):
                        if '.neon.tech' in part:
                            uri_parts[i-1] = uri_parts[i-1] + '-pooler'
                            break
                    self.SQLALCHEMY_DATABASE_URI = '.'.join(uri_parts)
                    logger.info("Enabled Neon connection pooling")
                    
                # Use higher concurrency for Neon's built-in pooler
                self._engine_options['pool_size'] = 10
                
        return self._engine_options

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