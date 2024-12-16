import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy import func, text
from models import Transaction, Account, db

logger = logging.getLogger(__name__)

def find_similar_transactions(description: str, transactions: List[Transaction]) -> List[Dict]:
    """Find similar transactions based on description matching"""
    try:
        matches = []
        description_lower = description.lower()
        
        for transaction in transactions:
            if not transaction.description:
                continue
                
            similarity = calculate_similarity(description_lower, transaction.description.lower())
            if similarity >= TEXT_THRESHOLD:
                matches.append({
                    'transaction': transaction,
                    'similarity': similarity,
                    'match_type': 'text'
                })
        
        return sorted(matches, key=lambda x: x['similarity'], reverse=True)[:5]
        
    except Exception as e:
        logger.error(f"Error finding similar transactions: {str(e)}")
        return []

def predict_account(description: str, explanation: str, accounts: List[Dict]) -> Optional[int]:
    """Predict account based on description and explanation patterns"""
    try:
        # Start with keyword matching
        keywords = {
            'salary': 'Income',
            'rent': 'Rent Expense',
            'fuel': 'Vehicle Expenses',
            'interest': 'Interest Income',
            'utilities': 'Utilities'
        }
        
        description_lower = description.lower()
        for keyword, category in keywords.items():
            if keyword in description_lower:
                matching_accounts = [
                    acc for acc in accounts 
                    if acc.get('category', '').lower() == category.lower()
                ]
                if matching_accounts:
                    return matching_accounts[0].get('id')
        
        return None
        
    except Exception as e:
        logger.error(f"Error predicting account: {str(e)}")
        return None

def suggest_explanation(description: str, similar_transactions: List[Dict]) -> Optional[str]:
    """Suggest explanation based on similar transactions"""
    try:
        # Get explanations from similar transactions
        explanations = []
        for match in similar_transactions:
            transaction = match.get('transaction')
            if transaction and transaction.explanation:
                explanations.append({
                    'explanation': transaction.explanation,
                    'similarity': match.get('similarity', 0)
                })
        
        if explanations:
            # Return the explanation with highest similarity
            best_match = max(explanations, key=lambda x: x['similarity'])
            return best_match['explanation']
            
        return None
        
    except Exception as e:
        logger.error(f"Error suggesting explanation: {str(e)}")
        return None

def calculate_similarity(str1: str, str2: str) -> float:
    """Calculate string similarity using multiple methods"""
    try:
        # Simple contains check
        if str1 in str2 or str2 in str1:
            return 0.9
            
        # Word overlap
        words1 = set(str1.split())
        words2 = set(str2.split())
        common_words = words1.intersection(words2)
        
        if not words1 or not words2:
            return 0.0
            
        overlap = len(common_words) / max(len(words1), len(words2))
        return overlap
        
    except Exception as e:
        logger.error(f"Error calculating similarity: {str(e)}")
        return 0.0

class PredictiveEngine:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def find_recurring_patterns(self, description: str, user_id: int) -> List[Dict]:
        """Find recurring patterns in historical transactions using multiple matching strategies"""
        try:
            patterns = []
            
            # 1. Exact match - highest confidence
            exact_matches = Transaction.query.filter(
                Transaction.user_id == user_id,
                func.lower(Transaction.description) == description.lower()
            ).order_by(Transaction.date.desc()).limit(5).all()
            
            for match in exact_matches:
                if match.account_id and match.explanation:
                    patterns.append({
                        'description': match.description,
                        'account_id': match.account_id,
                        'explanation': match.explanation,
                        'frequency': self._calculate_frequency(match, user_id),
                        'confidence': 0.95,  # High confidence for exact matches
                        'match_type': 'exact'
                    })
            
            # 2. Partial match - medium confidence
            if len(patterns) < 5:  # Only if we need more suggestions
                similar_transactions = Transaction.query.filter(
                    Transaction.user_id == user_id,
                    Transaction.description.ilike(f"%{description}%")
                ).order_by(Transaction.date.desc()).limit(10).all()
                
                for transaction in similar_transactions:
                    if transaction.account_id and transaction.explanation:
                        confidence = self._calculate_pattern_confidence(transaction, similar_transactions)
                        if confidence > 0.6:  # Only include if confidence is high enough
                            patterns.append({
                                'description': transaction.description,
                                'account_id': transaction.account_id,
                                'explanation': transaction.explanation,
                                'frequency': self._calculate_frequency(transaction, user_id),
                                'confidence': confidence * 0.8,  # Slightly lower confidence for partial matches
                                'match_type': 'partial'
                            })
            
            return sorted(patterns, key=lambda x: x['confidence'], reverse=True)
            
        except Exception as e:
            self.logger.error(f"Error finding patterns: {str(e)}")
            return []

    def apply_keyword_rules(self, description: str, amount: float) -> List[Dict]:
        """Apply keyword-based rules for transaction matching"""
        try:
            rules = [
                {
                    'keywords': ['salary', 'payroll', 'wage'],
                    'category': 'Income',
                    'confidence': 0.9
                },
                {
                    'keywords': ['rent', 'lease'],
                    'category': 'Rent Expense',
                    'confidence': 0.85
                },
                {
                    'keywords': ['fuel', 'petrol', 'gas'],
                    'category': 'Vehicle Expenses',
                    'confidence': 0.8
                }
            ]
            
            matches = []
            description_lower = description.lower()
            
            for rule in rules:
                if any(keyword in description_lower for keyword in rule['keywords']):
                    matches.append({
                        'category': rule['category'],
                        'confidence': rule['confidence'],
                        'match_type': 'keyword_rule',
                        'matched_keywords': [k for k in rule['keywords'] if k in description_lower]
                    })
            
            return matches
            
        except Exception as e:
            self.logger.error(f"Error applying keyword rules: {str(e)}")
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
        """Calculate confidence score using multiple factors"""
        try:
            if not similar_transactions:
                return 0.0
            
            # Base confidence from account usage
            same_account_count = sum(
                1 for t in similar_transactions 
                if t.account_id == transaction.account_id
            )
            account_confidence = same_account_count / len(similar_transactions)
            
            # Explanation consistency
            if transaction.explanation:
                same_explanation_count = sum(
                    1 for t in similar_transactions
                    if t.explanation and t.explanation.lower() == transaction.explanation.lower()
                )
                explanation_confidence = same_explanation_count / len(similar_transactions)
            else:
                explanation_confidence = 0.0
            
            # Recent usage bonus (more recent = higher confidence)
            try:
                latest_similar = max(t.date for t in similar_transactions)
                days_since_latest = (datetime.utcnow() - latest_similar).days
                recency_factor = max(0.5, 1 - (days_since_latest / 365))  # Decay over a year
            except Exception as e:
                self.logger.warning(f"Error calculating recency: {str(e)}")
                recency_factor = 0.5
            
            # Combined confidence score with weights
            confidence = (
                (account_confidence * 0.4) +      # 40% weight on account consistency
                (explanation_confidence * 0.4) +   # 40% weight on explanation consistency
                (recency_factor * 0.2)            # 20% weight on recency
            )
            
            return min(0.95, confidence)  # Cap at 0.95 to leave room for exact matches
            
        except Exception as e:
            self.logger.error(f"Error calculating pattern confidence: {str(e)}")
            return 0.0

    def get_hybrid_suggestions(
        self,
        description: str,
        amount: float,
        user_id: int,
        accounts: List[Account]
    ) -> Dict:
        """Get suggestions using all available methods in priority order"""
        try:
            # Start with pattern-based matches (fast and based on historical data)
            pattern_matches = self.find_recurring_patterns(description, user_id)
            
            # Apply keyword rules
            keyword_matches = self.apply_keyword_rules(description, amount)
            
            # Apply user-defined rules
            rule_matches = self.apply_user_rules(description, amount, user_id)
            
            # Only if we don't have high-confidence matches, use AI
            best_confidence = max(
                ([p['confidence'] for p in pattern_matches] +
                 [r['confidence'] for r in rule_matches] +
                 [0.0]),
                default=0.0
            )
            
            results = {
                'pattern_matches': pattern_matches,
                'keyword_matches': keyword_matches,
                'rule_matches': rule_matches,
                'ai_suggestions': []
            }
            
            # Preserve existing AI features
            if best_confidence < 0.8:
                similar_trans = find_similar_transactions(description, [])
                account_data = [
                    {'name': acc.name, 'category': acc.category, 'link': acc.link}
                    for acc in accounts
                ]
                ai_account = predict_account(description, '', account_data)
                ai_explanation = suggest_explanation(description, similar_trans)
                
                results['ai_suggestions'] = [{
                    'account_suggestion': ai_account,
                    'explanation_suggestion': ai_explanation,
                    'confidence': 0.7,
                    'source': 'ai'
                }]
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error getting hybrid suggestions: {str(e)}")
            return {
                'pattern_matches': [],
                'keyword_matches': [],
                'rule_matches': [],
                'ai_suggestions': []
            }

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
                
            # Add keyword-based suggestions
            for keyword in suggestions.get('keyword_matches', []):
                all_suggestions.append({
                    'account_id': None,  # Need to map category to account ID
                    'explanation': f"Based on keyword: {', '.join(keyword['matched_keywords'])}",
                    'confidence': keyword['confidence'] * 0.7  # Weight for keywords
                })
                
            # Add rule-based suggestions
            for rule in suggestions.get('rule_matches', []):
                all_suggestions.append({
                    'account_id': rule['account_id'],
                    'explanation': rule['explanation'],
                    'confidence': rule['confidence'] * 0.9  # Weight for rules
                })
                
            # Add AI suggestions with lower weight
            for ai_suggestion in suggestions.get('ai_suggestions', []):
                all_suggestions.append({
                    'account_id': ai_suggestion.get('account_suggestion'),
                    'explanation': ai_suggestion.get('explanation_suggestion'),
                    'confidence': (ai_suggestion.get('confidence', 0.7) * 0.6)  # Lower weight for AI
                })
                
            if not all_suggestions:
                return None, None
                
            # Sort by confidence and return best match
            best_match = max(all_suggestions, key=lambda x: x['confidence'])
            return best_match['account_id'], best_match['explanation']
            
        except Exception as e:
            self.logger.error(f"Error combining suggestions: {str(e)}")
            return None, None

# Constants for similarity thresholds
TEXT_THRESHOLD = 0.8
SEMANTIC_THRESHOLD = 0.7
