"""
Error handling blueprint configuration
"""
from flask import Blueprint

# Create blueprint for error handling
bp = Blueprint('errors', __name__)

# Import handlers after blueprint creation
from errors.routes import handle_404_error, handle_500_error

# Register error handlers
bp.register_error_handler(404, handle_404_error)
bp.register_error_handler(500, handle_500_error)