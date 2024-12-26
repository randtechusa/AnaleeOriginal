"""
Chat module for AI assistant functionality
Keeps chat functionality separate from core features
"""
from flask import Blueprint

# Create blueprint with proper prefix
chat = Blueprint('chat', __name__, url_prefix='/chat')

# Import routes after blueprint creation to avoid circular imports
from . import routes