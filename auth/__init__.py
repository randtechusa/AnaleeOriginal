"""
Authentication blueprint initialization.
Handles all authentication related functionality including login, 
password reset and MFA.
"""
from flask import Blueprint

# Create auth blueprint with url_prefix
auth = Blueprint('auth', __name__, url_prefix='/auth')

# Import routes after blueprint creation to avoid circular imports
from . import routes