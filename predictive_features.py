"""
Enhanced Predictive Features Module with comprehensive error handling and validation
"""
import logging
from typing import Dict, List, Optional, Any, Tuple
from difflib import SequenceMatcher
import numpy as np
from sqlalchemy import text
from datetime import datetime
from models import db, Transaction, Account

logger = logging.getLogger(__name__)

class PredictiveFeatures:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.TEXT_SIMILARITY_THRESHOLD = 0.7
        self.SEMANTIC_SIMILARITY_THRESHOLD = 0.95 #Added for semantic similarity check (Not implemented in original code)
        self.MAX_RETRIES = 3 # Added for retry mechanism (Not implemented in original code)
        self.MIN_DESCRIPTION_LENGTH = 3

    def validate_input(self, description: str, explanation: str = "") -> Tuple[bool, str]:
        """Validate input parameters"""
        try:
            if not isinstance(description, str):
                return False, "Description must be a string"
            if not description.strip():
                return False, "Description cannot be empty"
            if len(description.strip()) < self.MIN_DESCRIPTION_LENGTH:
                return False, f"Description must be at least {self.MIN_DESCRIPTION_LENGTH} characters"
            if explanation and not isinstance(explanation, str):
                return False, "Explanation must be a string"
            return True, "Valid input"
        except Exception as e:
            self.logger.error(f"Input validation error: {str(e)}")
            return False, f"Validation error: {str(e)}"

    def setup_logging(self):
        """Configure logging for the predictive features module"""
        handler = logging.FileHandler('predictive_features.log')
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    def find_similar_transactions(self, description: str) -> Dict[str, Any]:
        """Find similar transactions with comprehensive validation and error handling"""
        self.logger.info(f"ERF: Processing request for description: {description}")
        
        try:
            # Enhanced input validation
            is_valid, error_message = self.validate_input(description)
            if not is_valid:
                self.logger.error(f"ERF validation failed: {error_message}")
                return {
                    'success': False,
                    'error': error_message,
                    'error_code': 'INVALID_INPUT',
                    'validation_details': {
                        'description_length': len(description) if description else 0,
                        'required_length': self.MIN_DESCRIPTION_LENGTH
                    }
                }

            # Input sanitization
            description = description.strip()
            
            # Performance tracking
            start_time = datetime.now()
            processed_count = 0
            error_count = 0

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

                    if similarity >= self.TEXT_SIMILARITY_THRESHOLD: #Use the threshold from the class
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
                    self.logger.warning(f"Error processing transaction {transaction.id}: {str(tx_error)}")
                    continue

            similar_transactions.sort(key=lambda x: x['confidence'], reverse=True)
            similar_transactions = similar_transactions[:self.max_results]

            processing_time = (datetime.now() - start_time).total_seconds()
            self.logger.info(f"Found {len(similar_transactions)} similar transactions in {processing_time}s")

            return {
                'success': True,
                'similar_transactions': similar_transactions,
                'processing_time': processing_time,
                'total_compared': len(transactions)
            }

        except Exception as e:
            self.logger.error(f"Error finding similar transactions: {str(e)}", exc_info=True)
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
            self.logger.error(f"Error analyzing transaction patterns: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'error_code': 'PATTERN_ANALYSIS_ERROR'
            }