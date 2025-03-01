"""
Hybrid prediction module combining multiple approaches for account suggestions
"""
import logging
from typing import List, Dict, Any

class HybridPredictor:
    """
    Combines multiple prediction approaches to provide account suggestions:
    - Keyword matching
    - Pattern recognition
    - Historical data analysis
    """
    
    def __init__(self):
        """Initialize prediction components"""
        self.logger = logging.getLogger('hybrid_predictor')
        self.setup_logging()
        self._initialize_keyword_rules()
        
    def setup_logging(self):
        """Set up logging for the predictor"""
        logger = logging.getLogger('hybrid_predictor')
        if not logger.handlers:
            handler = logging.FileHandler('hybrid_predictor.log')
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            
    def _initialize_keyword_rules(self):
        """Initialize basic keyword rules for common categories"""
        self.keyword_rules = [
            {'keyword': 'office', 'account_name': 'Office Expenses', 'confidence': 0.85},
            {'keyword': 'rent', 'account_name': 'Rent Expense', 'confidence': 0.9},
            {'keyword': 'salary', 'account_name': 'Salaries Expense', 'confidence': 0.9},
            {'keyword': 'utilities', 'account_name': 'Utilities Expense', 'confidence': 0.85},
            {'keyword': 'phone', 'account_name': 'Telephone Expense', 'confidence': 0.8},
            {'keyword': 'insurance', 'account_name': 'Insurance Expense', 'confidence': 0.85},
            {'keyword': 'internet', 'account_name': 'Internet Expense', 'confidence': 0.8}
        ]
    
    def get_keyword_suggestions(self, description: str) -> List[Dict]:
        """Get suggestions based on keyword matching"""
        try:
            description = description.lower().strip()
            if not description:
                return []
                
            suggestions = []
            for rule in self.keyword_rules:
                if rule['keyword'] in description:
                    suggestions.append({
                        'category': rule['account_name'],
                        'confidence': rule['confidence'],
                        'match_type': 'keyword'
                    })
                    
            return suggestions
            
        except Exception as e:
            self.logger.error(f"Error in keyword suggestions: {str(e)}")
            return []
    
    def get_suggestions(self, 
                  description: str,
                  amount: float,
                  historical_data: List[Dict],
                  available_accounts: List[Dict]) -> List[Dict]:
        """
        Get suggestions using hybrid approach:
        1. Try pattern matching first
        2. If confidence is low, use AI predictions
        3. Combine results with confidence scores
        """
        try:
            # Get keyword-based suggestions first
            keyword_suggestions = self.get_keyword_suggestions(description)
            
            # For now, just return these
            return keyword_suggestions
            
        except Exception as e:
            self.logger.error(f"Error in hybrid suggestions: {str(e)}")
            return []
    
    def find_similar_transactions(self, description: str) -> Dict:
        """Find similar transactions based on description"""
        try:
            # Use keyword matches for now
            keyword_matches = self.get_keyword_suggestions(description)
            
            return {
                'success': True,
                'similar_transactions': keyword_matches,
                'analysis': {
                    'pattern_count': len(keyword_matches),
                    'confidence_avg': sum(m['confidence'] for m in keyword_matches) / len(keyword_matches) if keyword_matches else 0
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error finding similar transactions: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'similar_transactions': []
            }