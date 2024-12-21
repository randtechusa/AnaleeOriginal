from flask import Blueprint
from flask_login import login_required

# Create blueprint for error monitoring
errors = Blueprint('errors', __name__, url_prefix='/errors')

# Import routes after blueprint creation to avoid circular imports
from . import routes
