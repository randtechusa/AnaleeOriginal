from flask import Blueprint

suggestions = Blueprint('suggestions', __name__, url_prefix='/api/suggestions')

from . import routes
