"""
Bank statement upload module
Handles bank statement uploads separately from historical data
"""
from flask import Blueprint

bank_statements = Blueprint('bank_statements', __name__, url_prefix='/bank-statements')

# Import routes after blueprint creation to avoid circular imports
from . import routes  # noqa: E402