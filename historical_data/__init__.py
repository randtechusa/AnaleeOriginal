from flask import Blueprint

historical_data = Blueprint('historical_data', __name__, url_prefix='/historical-data')

from . import routes
