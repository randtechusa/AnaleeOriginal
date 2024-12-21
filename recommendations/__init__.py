from flask import Blueprint

recommendations = Blueprint('recommendations', __name__, url_prefix='/recommendations')

from . import routes
