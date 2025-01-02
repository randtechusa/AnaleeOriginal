"""
Models specific to bank statement processing
Keeps bank statement data separate from core modules and historical data
Implements secure isolation pattern
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Enum as SQLEnum, Text
from models import db, User, Account, Transaction, BankStatementUpload

# Import FinancialGoal from models
from models import FinancialGoal

# The bank statement upload model has been moved to the main models.py
# This file serves as a central point for importing models used in bank statements

__all__ = ['User', 'Account', 'Transaction', 'BankStatementUpload', 'FinancialGoal']