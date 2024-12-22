"""
Routes package initialization
Contains all route blueprints for the application
"""
from flask import Blueprint

# Create blueprints
main = Blueprint('main', __name__)

# Import routes after blueprint creation to avoid circular imports
from .main_routes import index, login, register, dashboard, logout, upload # Added import for upload
from .batch_processing import batch_processing

# Register routes with main blueprint (core functionality)
main.add_url_rule('/', view_func=index)
main.add_url_rule('/login', view_func=login, methods=['GET', 'POST'])
main.add_url_rule('/register', view_func=register, methods=['GET', 'POST'])
main.add_url_rule('/dashboard', view_func=dashboard)
main.add_url_rule('/logout', view_func=logout)
main.add_url_rule('/upload', view_func=upload, methods=['GET', 'POST'])  # Add upload route

# Note: batch_processing blueprint is registered directly in app.py