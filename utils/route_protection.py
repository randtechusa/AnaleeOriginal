import logging
from functools import wraps
from flask import current_app, flash, redirect, url_for
from flask_login import current_user

logger = logging.getLogger(__name__)

class RouteProtection:
    """Enforce route protection and environment separation"""
    
    @staticmethod
    def protect_production(f):
        """Decorator to protect production routes"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if current_app.config.get('ENV') == 'production':
                if not current_app.config.get('ALLOW_PRODUCTION_RULES', False):
                    logger.warning(f"Protected route {f.__name__} accessed in production")
                    flash('This operation is not allowed in production environment', 'warning')
                    return redirect(url_for('main.index'))
            return f(*args, **kwargs)
        return decorated_function
    
    @staticmethod
    def protect_data(f):
        """Decorator to protect data modifications"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if current_app.config.get('PROTECT_DATA', True):
                if not current_user.is_authenticated:
                    logger.warning(f"Unauthenticated data access attempt on {f.__name__}")
                    return redirect(url_for('main.login'))
                # Always allow users to modify their own rules
                if f.__name__ not in ['create_rule', 'edit_rule', 'delete_rule', 'toggle_rule']:
                    logger.warning(f"Unauthorized data modification attempt by user {current_user.id}")
                    flash('You do not have permission to modify data', 'warning')
                    return redirect(url_for('main.index'))
            return f(*args, **kwargs)
        return decorated_function
    
    @staticmethod
    def protect_completed_features(f):
        """Decorator to protect completed features"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            feature = f.__name__
            if feature in current_app.config.get('PROTECTED_FEATURES', []):
                logger.warning(f"Attempted modification of protected feature: {feature}")
                flash('This feature is protected and cannot be modified', 'warning')
                return redirect(url_for('main.index'))
            return f(*args, **kwargs)
        return decorated_function

    @staticmethod
    def verify_environment():
        """Verify current environment protection"""
        env = current_app.config.get('ENV', 'production')
        if env == 'production':
            if not current_app.config.get('PROTECT_PRODUCTION', True):
                logger.error("Production protection not enabled")
                return False
            if not current_app.config.get('PROTECT_DATA', True):
                logger.error("Data protection not enabled in production")
                return False
        return True
