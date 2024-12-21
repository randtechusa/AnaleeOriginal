from flask import Blueprint

risk_assessment = Blueprint('risk_assessment', __name__, url_prefix='/risk-assessment')

from . import routes
