import os
import logging
logger = logging.getLogger(__name__)
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', os.urandom(24).hex())
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TEMPLATES_AUTO_RELOAD = True
    
    # Environment Protection
    PROTECT_PRODUCTION = True  # Global flag to prevent production modifications
    STRICT_ENV_SEPARATION = True  # Enforce strict environment separation
    
    # Data Protection
    PROTECT_DATA = True  # Protect all data modifications
    PROTECT_CHART_OF_ACCOUNTS = True  # Protect chart of accounts from modifications
    PROTECT_COMPLETED_FEATURES = True  # Protect completed features
    
    # Feature Protection Settings
    PROTECTED_TABLES = ['account']  # Tables that cannot be modified
    PROTECTED_FEATURES = [
        'transaction_processing',
        'pattern_matching',
        'fuzzy_matching',
        'keyword_rules',
        'historical_analysis',
        'frequency_analysis',
        'statistical_analysis'
    ]  # Completed features that cannot be modified

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    ENV = 'production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)
    
    # Enhanced Production Protection
    PROTECT_PRODUCTION = True
    ALLOW_FEATURE_MODIFICATION = False
    ALLOW_DATA_MODIFICATION = False
    STRICT_ENV_SEPARATION = True
    
    # Production-specific settings
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 5,
        'pool_timeout': 30,
        'pool_recycle': 300,
        'pool_pre_ping': True
    }
    
    @classmethod
    def init_app(cls, app):
        """Production-specific initialization"""
        # Enhanced production protection
        app.config.update({
            'PREVENT_MODIFICATIONS': True,
            'PROTECT_CHART_OF_ACCOUNTS': True,
            'PROTECT_COMPLETED_FEATURES': True,
            'PROTECT_DATA': True,
            'READ_ONLY_TABLES': ['account', 'transaction', 'company_settings']
        })

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    ENV = 'development'
    
    # Database Configuration with Protection
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    if not SQLALCHEMY_DATABASE_URI:
        logger.error("Database URL is not set")
        raise ValueError("DATABASE_URL must be set for development environment")
    if SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)
    
    # Enhanced Development Protection
    PROTECT_PRODUCTION_DATA = True
    STRICT_ENV_SEPARATION = True
    PROTECT_CHART_OF_ACCOUNTS = True  # Protect chart of accounts
    ALLOW_FEATURE_MODIFICATION = False  # Protect completed features
    ALLOW_PRODUCTION_RULES = False  # Protect rules in development
    
    # Development-specific Protection
    PROTECTED_FEATURES = [
        'transaction_processing',
        'pattern_matching',
        'fuzzy_matching',
        'keyword_rules',
        'historical_analysis',
        'frequency_analysis',
        'statistical_analysis'
    ]
    
    # Development-specific settings
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 2,
        'echo': True,
        'echo_pool': True,
        'pool_pre_ping': True,
        'connect_args': {
            'connect_timeout': 10
        }
    }
    
    @classmethod
    def init_app(cls, app):
        """Development-specific initialization"""
        app.config.update({
            'PROTECT_COMPLETED_FEATURES': True,
            'PROTECT_CHART_OF_ACCOUNTS': True,
            'DEVELOPMENT_MODE': True,
            'PROTECTED_TABLES': ['account']  # Protect chart of accounts
        })

class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL', 'sqlite:///test.db')

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
