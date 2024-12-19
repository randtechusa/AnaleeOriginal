"""Rules management blueprint package

This module handles all rule-related functionality with strict environment separation
and data protection mechanisms.
"""
from flask import Blueprint, current_app

# Create blueprint with strict environment separation
rules = Blueprint('rules', __name__, url_prefix='/rules')

# Define protected routes for production environment
protected_routes = [
    'rules.create_rule',
    'rules.edit_rule',
    'rules.delete_rule',
    'rules.toggle_rule',
    'rules.update_priority'
]

# Import views
from .routes import (
    manage_rules,
    create_rule,
    toggle_rule,
    update_priority
)

# Register routes with proper error handling
def init_blueprint(blueprint):
    """Initialize blueprint routes with protection"""
    try:
        blueprint.add_url_rule('/', view_func=manage_rules, methods=['GET'])
        blueprint.add_url_rule('/create', view_func=create_rule, methods=['GET', 'POST'])
        blueprint.add_url_rule('/<int:rule_id>/toggle', view_func=toggle_rule, methods=['POST'])
        blueprint.add_url_rule('/<int:rule_id>/priority', view_func=update_priority, methods=['POST'])
        
        current_app.logger.info("Rules blueprint routes registered successfully")
    except Exception as e:
        current_app.logger.error(f"Failed to register rules blueprint routes: {str(e)}")
        raise

# Initialize routes
init_blueprint(rules)
