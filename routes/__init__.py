"""
Routes package initialization
Contains all route blueprints for the application
"""
from flask import Blueprint

# Create blueprints
main = Blueprint('main', __name__)

# Import routes after blueprint creation to avoid circular imports
from .main_routes import (
    index, login, register, dashboard, logout, upload, 
    analyze_list, icountant_interface, financial_insights
)
from .batch_processing import batch_processing

# Register routes with main blueprint (core functionality)
main.add_url_rule('/', view_func=index)
main.add_url_rule('/login', view_func=login, methods=['GET', 'POST'])
main.add_url_rule('/register', view_func=register, methods=['GET', 'POST'])
main.add_url_rule('/dashboard', view_func=dashboard)
main.add_url_rule('/logout', view_func=logout)
main.add_url_rule('/upload', view_func=upload, methods=['GET', 'POST'])
main.add_url_rule('/analyze/list', view_func=analyze_list, methods=['GET'])
main.add_url_rule('/icountant', view_func=icountant_interface, methods=['GET', 'POST'])
main.add_url_rule('/financial-insights', view_func=financial_insights, methods=['GET'])

# Note: batch_processing blueprint is registered directly in app.py