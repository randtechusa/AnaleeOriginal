import os
from datetime import timedelta

class Config:
    """Base configuration"""
    # Basic Configuration
    SECRET_KEY = os.environ.get('SECRET_KEY', os.urandom(24).hex())
    TEMPLATES_AUTO_RELOAD = True

    # Database Configuration
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    db_url = os.environ.get('DATABASE_URL')
    
    # Enhanced database connection handling
    try:
        if db_url:
            # Convert postgres:// to postgresql:// if needed
            if db_url.startswith('postgres://'):
                db_url = db_url.replace('postgres://', 'postgresql://', 1)
            SQLALCHEMY_DATABASE_URI = db_url
        else:
            # Explicit SQLite fallback
            SQLALCHEMY_DATABASE_URI = 'sqlite:///dev.db'
            
        # Adjust engine options based on database type
        if SQLALCHEMY_DATABASE_URI.startswith('sqlite'):
            SQLALCHEMY_ENGINE_OPTIONS = {
                'pool_pre_ping': True,
                'pool_recycle': 280,
                'connect_args': {'timeout': 15}
            }
    except Exception as e:
        # Emergency fallback to SQLite
        SQLALCHEMY_DATABASE_URI = 'sqlite:///dev.db'
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': True,
            'connect_args': {'timeout': 15}
        }

    # Essential database connection settings
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_size': 1,
        'max_overflow': 0,
        'pool_timeout': 10,
        'pool_recycle': 1800,
        'connect_args': {
            'connect_timeout': 5,
            'application_name': 'icountant'
        }
    }

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False

    # Pattern Matching Configuration
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

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:test@localhost/test'

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}