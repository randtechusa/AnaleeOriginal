"""
Enhanced Predictive Features Module with comprehensive error handling and validation
"""
import logging
from typing import Dict, List, Optional, Any
from difflib import SequenceMatcher
import numpy as np
from sqlalchemy import text
from datetime import datetime
from models import db, Transaction, Account

logger = logging.getLogger(__name__)

class PredictiveFeatures:
    def __init__(self):
        self.confidence_threshold = 0.7
        self.min_description_length = 3
        self.max_results = 5
        self.setup_logging()

    def setup_logging(self):
        """Configure logging for the predictive features module"""
        handler = logging.FileHandler('predictive_features.log')
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    def validate_input(self, description: str, min_length: int = 3) -> bool:
        """Validate input parameters"""
        if not description or not isinstance(description, str):
            logger.error(f"Invalid description: {description}")
            return False
        if len(description.strip()) < min_length:
            logger.error(f"Description too short: {description}")
            return False
        return True

    def find_similar_transactions(self, description: str) -> Dict[str, Any]:
        """Find similar transactions with enhanced validation and error handling"""
        try:
            if not self.validate_input(description):
                return {
                    'success': False,
                    'error': 'Invalid or too short description',
                    'error_code': 'INVALID_INPUT'
                }

            similar_transactions = []
            start_time = datetime.now()

            transactions = Transaction.query.filter(
                Transaction.explanation.isnot(None),
                Transaction.description.isnot(None)
            ).all()

            for transaction in transactions:
                try:
                    similarity = SequenceMatcher(
                        None,
                        description.lower(),
                        transaction.description.lower()
                    ).ratio()

                    if similarity >= self.confidence_threshold:
                        similar_transactions.append({
                            'id': transaction.id,
                            'description': transaction.description,
                            'explanation': transaction.explanation,
                            'confidence': round(similarity, 2),
                            'account_id': transaction.account_id,
                            'date': transaction.date.isoformat() if transaction.date else None,
                            'amount': float(transaction.amount) if transaction.amount else 0
                        })
                except Exception as tx_error:
                    logger.warning(f"Error processing transaction {transaction.id}: {str(tx_error)}")
                    continue

            similar_transactions.sort(key=lambda x: x['confidence'], reverse=True)
            similar_transactions = similar_transactions[:self.max_results]

            processing_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"Found {len(similar_transactions)} similar transactions in {processing_time}s")

            return {
                'success': True,
                'similar_transactions': similar_transactions,
                'processing_time': processing_time,
                'total_compared': len(transactions)
            }

        except Exception as e:
            logger.error(f"Error finding similar transactions: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'error_code': 'PROCESSING_ERROR'
            }

    def get_transaction_patterns(self, user_id: int) -> Dict[str, Any]:
        """Analyze transaction patterns for a user"""
        try:
            if not isinstance(user_id, int) or user_id <= 0:
                return {'success': False, 'error': 'Invalid user ID'}

            transactions = Transaction.query.filter_by(user_id=user_id).all()
            if not transactions:
                return {'success': False, 'error': 'No transactions found'}

            patterns = {
                'frequent_descriptions': {},
                'amount_ranges': {},
                'temporal_patterns': {}
            }

            for transaction in transactions:
                desc = transaction.description.lower() if transaction.description else 'unknown'
                patterns['frequent_descriptions'][desc] = patterns['frequent_descriptions'].get(desc, 0) + 1

                amount = float(transaction.amount) if transaction.amount else 0
                range_key = f"{int(amount/1000)}k-{int(amount/1000)+1}k"
                patterns['amount_ranges'][range_key] = patterns['amount_ranges'].get(range_key, 0) + 1

                if transaction.date:
                    month_key = transaction.date.strftime('%B')
                    patterns['temporal_patterns'][month_key] = patterns['temporal_patterns'].get(month_key, 0) + 1

            return {
                'success': True,
                'patterns': patterns,
                'total_analyzed': len(transactions)
            }

        except Exception as e:
            logger.error(f"Error analyzing transaction patterns: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'error_code': 'PATTERN_ANALYSIS_ERROR'
            }