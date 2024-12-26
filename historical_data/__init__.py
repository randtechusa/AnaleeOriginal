"""
Historical Data Blueprint Configuration
Handles historical financial data processing with enhanced security
"""

from flask import Blueprint
from flask_login import login_required

# Create blueprint with proper URL prefix and import name
historical_data = Blueprint('historical_data', __name__, 
                          url_prefix='/historical-data')

# Protect all routes by default using login_required
@historical_data.before_request
@login_required
def require_login():
    """Ensure all routes require authentication"""
    pass

# Import routes after blueprint creation to avoid circular imports
from . import routes