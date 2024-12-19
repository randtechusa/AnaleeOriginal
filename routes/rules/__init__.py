"""Rules management blueprint package

This module handles all rule-related functionality with strict environment separation
and data protection mechanisms.
"""
import logging
import os
from flask import Blueprint, current_app
from flask_login import login_required

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create blueprint with strict environment separation and protection
rules = Blueprint('rules', __name__, url_prefix='/rules')

# Enhanced environment protection
PROTECT_DATA = os.environ.get('PROTECT_DATA', 'true').lower() == 'true'
PROTECT_CHART_OF_ACCOUNTS = os.environ.get('PROTECT_CHART_OF_ACCOUNTS', 'true').lower() == 'true'
PROTECT_COMPLETED_FEATURES = os.environ.get('PROTECT_COMPLETED_FEATURES', 'true').lower() == 'true'

# Define protected routes for production environment
protected_routes = [
    'rules.create_rule',
    'rules.edit_rule',
    'rules.delete_rule',
    'rules.toggle_rule',
    'rules.update_priority'
]

# Import views after blueprint creation
from .routes import (
    manage_rules,
    create_rule,
    toggle_rule,
    update_priority
)

def init_routes():
    """Initialize routes with proper environment protection"""
    try:
        # Verify environment protection
        if current_app.config.get('ENV') == 'production':
            if not current_app.config.get('PROTECT_DATA'):
                logger.error("Data protection not enabled in production")
                return False

        # Register routes with proper error handling
        rules.add_url_rule('/', view_func=manage_rules, methods=['GET'])
        rules.add_url_rule('/create', view_func=create_rule, methods=['GET', 'POST'])
        rules.add_url_rule('/<int:rule_id>/toggle', view_func=toggle_rule, methods=['POST'])
        rules.add_url_rule('/<int:rule_id>/priority', view_func=update_priority, methods=['POST'])
        
        logger.info("Rules blueprint routes registered successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to register rules blueprint routes: {str(e)}")
        return False

# Initialize routes with protection - moved to app.py for proper app context

def init_blueprint(blueprint):
    """Initialize blueprint with proper protection"""
    try:
        # Verify environment protection
        if current_app.config.get('ENV') == 'production':
            if not current_app.config.get('PROTECT_DATA'):
                logger.error("Data protection not enabled in production")
                return False
            
        return init_routes()
    except Exception as e:
        logger.error(f"Failed to initialize rules blueprint: {str(e)}")
        return False
