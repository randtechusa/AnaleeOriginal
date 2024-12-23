"""
Bank Statement Upload Module
Handles all bank statement related functionality including:
- File upload and validation
- Statement processing
- Data extraction and storage
"""
from flask import Blueprint

bank_statements = Blueprint('bank_statements', __name__, url_prefix='/bank-statements')

from . import routes  # noqa
