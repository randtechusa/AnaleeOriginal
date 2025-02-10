"""
Authentication blueprint initialization
Handles user authentication and related functionality
"""
from flask import Blueprint

bp = Blueprint('auth', __name__, url_prefix='/auth')

from auth import routes