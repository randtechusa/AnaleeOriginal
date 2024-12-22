"""
Routes package initialization
Contains all route blueprints for the application
"""
from flask import Blueprint

# Create blueprints
main = Blueprint('main', __name__)
batch_processing = Blueprint('batch_processing', __name__, url_prefix='/batch-process')

# Import routes after blueprint creation to avoid circular imports
from .batch_processing import batch_process_page, process_transactions
from .main_routes import index, login, register, dashboard, logout

# Register routes with main blueprint (core functionality)
main.add_url_rule('/', view_func=index)
main.add_url_rule('/login', view_func=login, methods=['GET', 'POST'])
main.add_url_rule('/register', view_func=register, methods=['GET', 'POST'])
main.add_url_rule('/dashboard', view_func=dashboard)
main.add_url_rule('/logout', view_func=logout)

# Register batch processing routes (new feature)
batch_processing.add_url_rule('/', view_func=batch_process_page, methods=['GET'])
batch_processing.add_url_rule('/process', view_func=process_transactions, methods=['POST'])