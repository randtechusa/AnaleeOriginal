"""
Chat module for AI assistant functionality
Keeps chat functionality separate from core features
"""
from flask import Blueprint

# Create blueprint with proper prefix
chat = Blueprint('chat', __name__)

# Import routes after blueprint creation to avoid circular imports
from . import routes