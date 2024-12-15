import logging
import re
from typing import List, Dict, Optional, Tuple
from models import Transaction, Account
from sqlalchemy import func
from datetime import datetime, timedelta
from ai_utils import find_similar_transactions, predict_account, suggest_explanation

logger = logging.getLogger(__name__)

class PredictiveEngine:
    """Enhanced predictive engine combining pattern matching, rules, and AI"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.rules_cache = {}
        self.pattern_cache = {}
        
    def find_recurring_patterns(self, description: str, user_id: int) -> List[Dict]:
        """Find recurring patterns in historical transactions"""
        try:
            # Query for transactions with similar descriptions
            similar_transactions = Transaction.query.filter(
                Transaction.user_id == user_id,
                Transaction.description.ilike(f"%{description}%")
            ).order_by(Transaction.date.desc()).limit(10).all()
            
            patterns = []
            for transaction in similar_transactions:
                if transaction.account_id and transaction.explanation:
                    patterns.append({
                        'description': transaction.description,
                        'account_id': transaction.account_id,
                        'explanation': transaction.explanation,
                        'frequency': self._calculate_frequency(transaction, user_id),
                        'confidence': self._calculate_pattern_confidence(transaction, similar_transactions)
                    })
            
            return patterns
            
        except Exception as e:
            self.logger.error(f"Error finding patterns: {str(e)}")
            return []
            
    def _calculate_frequency(self, transaction: Transaction, user_id: int) -> int:
        """Calculate how frequently this pattern appears"""
        try:
            count = Transaction.query.filter(
                Transaction.user_id == user_id,
                Transaction.description.ilike(f"%{transaction.description}%")
            ).count()
            return count
        except Exception as e:
            self.logger.error(f"Error calculating frequency: {str(e)}")
            return 0
            
    def _calculate_pattern_confidence(self, transaction: Transaction, similar_transactions: List[Transaction]) -> float:
        """Calculate confidence score for pattern matching"""
        try:
            if not similar_transactions:
                return 0.0
                
            # Count how many similar transactions used the same account
            same_account_count = sum(
                1 for t in similar_transactions 
                if t.account_id == transaction.account_id
            )
            
            return same_account_count / len(similar_transactions)
            
        except Exception as e:
            self.logger.error(f"Error calculating pattern confidence: {str(e)}")
            return 0.0
            
    def apply_user_rules(self, description: str, amount: float, user_id: int) -> List[Dict]:
        """Apply user-defined rules for categorization"""
        try:
            rules = self._get_user_rules(user_id)
            matches = []
            
            for rule in rules:
                if self._rule_matches(rule, description, amount):
                    matches.append({
                        'account_id': rule['account_id'],
                        'explanation': rule.get('explanation', ''),
                        'confidence': rule.get('confidence', 0.8),
                        'rule_id': rule['id']
                    })
            
            return matches
            
        except Exception as e:
            self.logger.error(f"Error applying rules: {str(e)}")
            return []
            
    def _get_user_rules(self, user_id: int) -> List[Dict]:
        """Get user-defined rules from cache or database"""
        # TODO: Implement actual rule storage
        # For now, return example rules
        return [
            {
                'id': 1,
                'pattern': r'(?i)fuel|petrol|gas station',
                'account_id': 1,  # Vehicle Expenses account
                'explanation': 'Fuel expense',
                'confidence': 0.9
            }
        ]
        
    def _rule_matches(self, rule: Dict, description: str, amount: float) -> bool:
        """Check if a rule matches the transaction"""
        try:
            pattern = rule['pattern']
            return bool(re.search(pattern, description, re.IGNORECASE))
        except Exception as e:
            self.logger.error(f"Error matching rule: {str(e)}")
            return False
            
    def get_hybrid_suggestions(
        self,
        description: str,
        amount: float,
        user_id: int,
        accounts: List[Account]
    ) -> Dict:
        """Get suggestions using all available methods"""
        try:
            results = {
                'pattern_matches': self.find_recurring_patterns(description, user_id),
                'rule_matches': self.apply_user_rules(description, amount, user_id),
                'ai_suggestions': []  # Will be populated with AI results
            }
            
            # Get AI suggestions using existing functions
            account_data = [
                {'name': acc.name, 'category': acc.category, 'link': acc.link}
                for acc in accounts
            ]
            
            # Preserve existing AI features
            similar_trans = find_similar_transactions(description, [])
            ai_account = predict_account(description, '', account_data)
            ai_explanation = suggest_explanation(description, similar_trans)
            
            results['ai_suggestions'] = [{
                'account_suggestion': ai_account,
                'explanation_suggestion': ai_explanation,
                'confidence': 0.7
            }]
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error getting hybrid suggestions: {str(e)}")
            return {
                'pattern_matches': [],
                'rule_matches': [],
                'ai_suggestions': []
            }
            
    def combine_suggestions(self, suggestions: Dict) -> Tuple[Optional[int], Optional[str]]:
        """Combine and rank all suggestions to provide best matches"""
        try:
            all_suggestions = []
            
            # Add pattern-based suggestions
            for pattern in suggestions.get('pattern_matches', []):
                all_suggestions.append({
                    'account_id': pattern['account_id'],
                    'explanation': pattern['explanation'],
                    'confidence': pattern['confidence'] * 0.8  # Weight for patterns
                })
                
            # Add rule-based suggestions
            for rule in suggestions.get('rule_matches', []):
                all_suggestions.append({
                    'account_id': rule['account_id'],
                    'explanation': rule['explanation'],
                    'confidence': rule['confidence'] * 0.9  # Weight for rules
                })
                
            # Add AI suggestions
            for ai_suggestion in suggestions.get('ai_suggestions', []):
                all_suggestions.append({
                    'account_id': ai_suggestion.get('account_suggestion'),
                    'explanation': ai_suggestion.get('explanation_suggestion'),
                    'confidence': ai_suggestion.get('confidence', 0.7)
                })
                
            if not all_suggestions:
                return None, None
                
            # Sort by confidence and return best match
            best_match = max(all_suggestions, key=lambda x: x['confidence'])
            return best_match['account_id'], best_match['explanation']
            
        except Exception as e:
            self.logger.error(f"Error combining suggestions: {str(e)}")
            return None, None
