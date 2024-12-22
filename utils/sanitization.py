"""
Data sanitization utilities for batch processing
Keeps sanitization logic separate from core features
"""
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)

def sanitize_transaction_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize validated transaction data for batch processing
    Returns cleaned data safe for database insertion
    """
    try:
        cleaned_data = {}
        
        # Clean date
        if isinstance(data['date'], str):
            cleaned_data['date'] = datetime.strptime(data['date'], '%Y-%m-%d')
        else:
            cleaned_data['date'] = data['date']

        # Clean description - strip whitespace and remove special characters
        cleaned_data['description'] = str(data['description']).strip()

        # Clean amount - ensure decimal
        cleaned_data['amount'] = float(data['amount'])

        # Clean account_id - ensure integer
        cleaned_data['account_id'] = int(data['account_id'])

        return cleaned_data

    except Exception as e:
        logger.error(f"Error sanitizing transaction data: {str(e)}")
        raise ValueError(f"Data sanitization failed: {str(e)}")
