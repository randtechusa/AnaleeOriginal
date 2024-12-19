from flask import Blueprint
from flask_login import login_required

reports = Blueprint('reports', __name__, url_prefix='/reports')

# Import routes after blueprint creation to avoid circular imports
from . import routes
