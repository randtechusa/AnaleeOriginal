"""
Models specific to bank statement processing
Keeps bank statement data separate from core modules and historical data
Implements secure isolation pattern
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Enum as SQLEnum
from models import db, BankStatementUpload

# The BankStatementUpload model has been moved to models.py to avoid circular imports
# This file is kept as a placeholder for future bank statement specific models