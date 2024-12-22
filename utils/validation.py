"""
Data validation utilities for batch processing
Keeps validation logic separate from core features
"""
import logging
from datetime import datetime
from typing import Dict, Any
import pandas as pd

logger = logging.getLogger(__name__)

def validate_transaction_data(row_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate incoming transaction data from batch upload
    Returns validation result with errors if any
    """
    errors = []
    try:
        # Required fields
        required_fields = ['date', 'description', 'amount', 'account_id']
        for field in required_fields:
            if field not in row_data or pd.isna(row_data[field]):
                errors.append(f"Missing required field: {field}")

        # Validate date format
        try:
            if 'date' in row_data and not pd.isna(row_data['date']):
                if isinstance(row_data['date'], str):
                    datetime.strptime(row_data['date'], '%Y-%m-%d')
                elif not isinstance(row_data['date'], datetime):
                    errors.append("Invalid date format")
        except ValueError:
            errors.append("Invalid date format")

        # Validate amount
        try:
            if 'amount' in row_data and not pd.isna(row_data['amount']):
                amount = float(row_data['amount'])
        except (ValueError, TypeError):
            errors.append("Invalid amount format")

        # Validate account_id
        try:
            if 'account_id' in row_data and not pd.isna(row_data['account_id']):
                account_id = int(row_data['account_id'])
                if account_id <= 0:
                    errors.append("Invalid account ID")
        except (ValueError, TypeError):
            errors.append("Invalid account ID format")

        return {
            'is_valid': len(errors) == 0,
            'data': row_data if len(errors) == 0 else None,
            'errors': errors
        }

    except Exception as e:
        logger.error(f"Error validating transaction data: {str(e)}")
        return {
            'is_valid': False,
            'data': None,
            'errors': [f"Validation error: {str(e)}"]
        }