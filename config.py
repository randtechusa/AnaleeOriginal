import os
from datetime import timedelta

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(24).hex()

    # Database configuration with enhanced SQLite fallback
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    
    def init_sqlite():
        sqlite_path = os.path.join(os.getcwd(), 'instance', 'app.db')
        os.makedirs('instance', exist_ok=True)
        return f'sqlite:///{sqlite_path}'

    if not SQLALCHEMY_DATABASE_URI:
        SQLALCHEMY_DATABASE_URI = init_sqlite()
    else:
        if SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
            SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://')
        
        try:
            from sqlalchemy import create_engine, text
            engine = create_engine(SQLALCHEMY_DATABASE_URI, pool_pre_ping=True)
            with engine.connect() as conn:
                conn.execute(text('SELECT 1'))
        except Exception as e:
            print(f"Warning: Primary database connection failed: {e}")
            print("Falling back to SQLite database")
            SQLALCHEMY_DATABASE_URI = init_sqlite()
            
    # Configure SQLAlchemy pool settings
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 5,
        'pool_timeout': 30,
        'pool_recycle': 1800,
        'pool_pre_ping': True
    }

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Database connection pool settings
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 5,
        'pool_timeout': 30,
        'pool_recycle': 1800,
        'pool_pre_ping': True
    }

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