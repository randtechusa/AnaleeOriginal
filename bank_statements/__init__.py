"""
Bank statement upload module
Handles bank statement uploads separately from historical data
"""
from flask import Blueprint

bank_statements = Blueprint('bank_statements', __name__, url_prefix='/bank-statements')

from . import routes
