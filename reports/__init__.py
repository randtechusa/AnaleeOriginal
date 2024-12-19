from flask import Blueprint
from flask_login import login_required

# Create blueprint without url_prefix (will be set during registration)
reports = Blueprint('reports', __name__)

# Import routes after blueprint creation to avoid circular imports
from . import routes
