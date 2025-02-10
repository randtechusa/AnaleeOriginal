import os
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
import time
from datetime import timedelta

def get_db_url():
    """Get database URL with enhanced retry logic and fallback"""
    max_retries = 5
    retry_delay = 3
    
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        return 'sqlite:///instance/dev.db'

    # Convert old postgres:// URLs to postgresql://
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    for attempt in range(max_retries):
        try:
            engine = create_engine(database_url, pool_pre_ping=True)
            with engine.connect() as conn:
                conn.execute("SELECT 1")
            return database_url

        except (OperationalError, ValueError) as e:
            if attempt == max_retries - 1:
                # If all retries failed, return None to trigger SQLite fallback
                return None
            time.sleep(retry_delay)

    return None

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(24).hex()

    # Try PostgreSQL first, fallback to SQLite
    SQLALCHEMY_DATABASE_URI = get_db_url() or 'sqlite:///instance/dev.db'

    # SQLAlchemy configuration
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_size': 1,
        'max_overflow': 0,
        'pool_recycle': 1800
    }

    # File upload configuration
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=60)
    SESSION_TYPE = 'filesystem'

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False

    # Transaction pattern matching configuration
    PATTERN_MATCHING = {
        'min_similarity_score': 0.85,
        'max_suggestions': 5,
        'cache_timeout': timedelta(hours=1),
        'use_ai_threshold': 0.7
    }

    # AI Configuration
    AI_CONFIG = {
        'max_retries': 3,
        'timeout': 30,
        'batch_size': 5,
        'confidence_threshold': 0.85
    }

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False

    # Override engine options for production
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_size': 5,
        'max_overflow': 10,
        'pool_recycle': 1800
    }

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'  # Use in-memory database for testing

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}