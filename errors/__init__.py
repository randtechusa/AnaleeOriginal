"""
Error handling blueprint configuration
"""
from flask import Blueprint

# Create blueprint for error handling
bp = Blueprint('errors', __name__)

# Import routes after blueprint creation to avoid circular imports
from . import routes