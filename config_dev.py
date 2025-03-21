import os
from datetime import timedelta

# Development-specific configuration
class DevelopmentConfig:
    # Basic Configuration
    DEBUG = True
    TESTING = False

    # Security Settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')

    # Database Configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///instance/dev.db')
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

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

    # Feature Flags for Development
    FEATURES = {
        'exact_matching': True,
        'fuzzy_matching': True,
        'keyword_rules': True,
        'historical_patterns': True,
        'amount_patterns': True,
        'ai_fallback': True
    }

config = DevelopmentConfig()