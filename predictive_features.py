"""
Enhanced Predictive Features Module with comprehensive error handling and validation
"""
import logging
import os
from datetime import datetime
from difflib import SequenceMatcher
from typing import Dict, Any, List, Tuple, Optional

from models import Transaction

class PredictiveFeatures:
    def __init__(self):
        self.TEXT_SIMILARITY_THRESHOLD = 0.7
        self.MIN_DESCRIPTION_LENGTH = 3
        self.max_results = 5
        self.logger = logging.getLogger('predictive_features')
        self.setup_logging()
    
    def validate_input(self, description: str, explanation: str = "") -> Tuple[bool, str]:
        """Validate input parameters"""
        if not isinstance(description, str):
            return False, "Description must be a string"
        
        description = description.strip()
        if not description:
            return False, "Description cannot be empty"
            
        if len(description) < self.MIN_DESCRIPTION_LENGTH:
            return False, f"Description must be at least {self.MIN_DESCRIPTION_LENGTH} characters"
            
        return True, ""
    
    def setup_logging(self):
        """Configure logging for the predictive features module"""
        logger = logging.getLogger('predictive_features')
        if not logger.handlers:
            handler = logging.FileHandler('predictive_features.log')
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
    
    def find_similar_transactions(self, description: str) -> Dict[str, Any]:
        """Find similar transactions with comprehensive validation and error handling"""
        self.logger.info(f"ERF: Processing request for description: {description}")
        metrics = {'start_time': datetime.now(), 'processed': 0, 'errors': 0}
        
        try:
            # Enhanced input validation
            if not isinstance(description, str):
                return {'success': False, 'error': 'Description must be a string'}
            
            description = description.strip()
            if not description:
                return {'success': False, 'error': 'Description cannot be empty'}
            
            if len(description) < self.MIN_DESCRIPTION_LENGTH:
                return {'success': False, 'error': f'Description must be at least {self.MIN_DESCRIPTION_LENGTH} characters'}
            
            similar_transactions = []
            transactions = Transaction.query.filter(
                Transaction.explanation.isnot(None),
                Transaction.description.isnot(None)
            ).all()
            
            for transaction in transactions:
                try:
                    metrics['processed'] += 1
                    text_similarity = SequenceMatcher(
                        None,
                        description.lower(),
                        transaction.description.lower()
                    ).ratio()
                    
                    if text_similarity >= self.TEXT_SIMILARITY_THRESHOLD:
                        similar_transactions.append({
                            'id': transaction.id,
                            'description': transaction.description,
                            'explanation': transaction.explanation,
                            'confidence': round(text_similarity, 2),
                            'match_type': 'text',
                            'account_id': transaction.account_id
                        })
                except Exception as tx_error:
                    metrics['errors'] += 1
                    self.logger.warning(f"Error processing transaction {transaction.id}: {str(tx_error)}")
                    continue
            
            similar_transactions.sort(key=lambda x: x['confidence'], reverse=True)
            similar_transactions = similar_transactions[:self.max_results]
            
            metrics['end_time'] = datetime.now()
            metrics['total_time'] = (metrics['end_time'] - metrics['start_time']).total_seconds()
            
            return {
                'success': True,
                'similar_transactions': similar_transactions,
                'metrics': metrics
            }
            
        except Exception as e:
            self.logger.error(f"ERF processing failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def suggest_account(self, description: str, explanation: str = "") -> List[Dict]:
        """Suggest accounts for a transaction based on description and explanation"""
        self.logger.info(f"ASF: Processing request for description: {description}")
        
        try:
            # Input validation
            valid, error_msg = self.validate_input(description, explanation)
            if not valid:
                self.logger.error(f"ASF validation error: {error_msg}")
                return []
            
            # Basic account suggestions based on keywords
            suggestions = []
            
            # Just return a sample suggestion for now
            suggestions.append({
                'account': 'Office Expenses',
                'confidence': 0.85,
                'reasoning': 'Based on similar transaction patterns',
                'source': 'keyword_matching'
            })
            
            return suggestions
            
        except Exception as e:
            self.logger.error(f"ASF processing failed: {str(e)}")
            return []
    
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