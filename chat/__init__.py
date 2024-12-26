"""
Chat module for AI assistant functionality
Keeps chat functionality separate from core features
"""
from flask import Blueprint

# Create blueprint with proper URL prefix and template folder
chat = Blueprint('chat', __name__, 
                url_prefix='/chat',
                template_folder='../templates/chat')

# Import routes after blueprint creation to avoid circular imports
from . import routes