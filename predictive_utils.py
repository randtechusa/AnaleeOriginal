import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy import func, text
from models import Transaction, Account, db

logger = logging.getLogger(__name__)

def find_similar_transactions(description: str, transactions: List[Transaction]) -> Tuple[bool, str, List[Dict]]:
    """Find similar transactions using pattern matching and frequency analysis with enhanced validation"""
    logger = logging.getLogger(__name__)
    
    try:
        # Input validation
        if not isinstance(description, str) or not description.strip():
            return False, "Invalid description", []
            
        if not isinstance(transactions, list):
            return False, "Invalid transactions list", []
            
        matches = []
        processed_count = 0
        error_count = 0
        
        # Track metrics for logging
        total_transactions = len(transactions)
        start_time = time.time()
        description_lower = description.lower().strip()
        frequency_map = {}
        
        # First pass: Build frequency map and find direct matches
        for transaction in transactions:
            if not transaction.description:
                continue
                
            # Update frequency map
            trans_desc = transaction.description.lower().strip()
            frequency_map[trans_desc] = frequency_map.get(trans_desc, 0) + 1
            
            # Calculate similarity
            similarity = calculate_similarity(description_lower, trans_desc)
            
            if similarity >= TEXT_THRESHOLD:
                # Boost score based on frequency
                frequency_boost = min(0.1, frequency_map[trans_desc] / 10)
                adjusted_similarity = min(0.99, similarity + frequency_boost)
                
                matches.append({
                    'transaction': transaction,
                    'similarity': adjusted_similarity,
                    'match_type': 'pattern',
                    'frequency': frequency_map[trans_desc]
                })
        
        # Second pass: Look for pattern matches in explanations
        for transaction in transactions:
            if not transaction.explanation or transaction in [m['transaction'] for m in matches]:
                continue
                
            explanation_similarity = calculate_similarity(description_lower, 
                                                       transaction.explanation.lower().strip())
            
            if explanation_similarity >= SEMANTIC_THRESHOLD:
                matches.append({
                    'transaction': transaction,
                    'similarity': explanation_similarity * 0.9,  # Slightly lower confidence for explanation matches
                    'match_type': 'semantic',
                    'frequency': frequency_map.get(transaction.description.lower().strip(), 0)
                })
        
        # Sort by similarity and frequency
        matches.sort(key=lambda x: (x['similarity'], x['frequency']), reverse=True)
        return matches[:5]  # Return top 5 matches
        
    except Exception as e:
        logger.error(f"Error finding similar transactions: {str(e)}")
        return []

def predict_account(description: str, explanation: str, accounts: List[Dict]) -> Optional[int]:
    """Predict account based on description and explanation patterns with enhanced validation"""
    try:
        # Input validation with detailed logging
        if not isinstance(description, str) or not description.strip():
            logger.error("Invalid description provided to account prediction")
            return None
            
        if not isinstance(accounts, list) or not accounts:
            logger.error("No valid accounts provided for prediction")
            return None
            
        # Enhanced keyword matching with validation
        keywords = {
            'salary': 'Income',
            'rent': 'Rent Expense',
            'fuel': 'Vehicle Expenses',
            'interest': 'Interest Income',
            'utilities': 'Utilities',
            'insurance': 'Insurance Expense',
            'maintenance': 'Maintenance Expense',
            'supplies': 'Office Supplies',
            'advertising': 'Marketing Expense'
        }
        
        # Validate accounts structure
        valid_accounts = [
            acc for acc in accounts 
            if isinstance(acc, dict) and 
            'id' in acc and 
            'category' in acc and 
            isinstance(acc['category'], str)
        ]
        
        if not valid_accounts:
            logger.error("No valid accounts found after validation")
            return None
        
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
        str1 = str1.lower().strip()
        str2 = str2.lower().strip()
        
        # Exact match
        if str1 == str2:
            return 1.0
            
        # Simple contains check
        if str1 in str2 or str2 in str1:
            return 0.9
            
        # Word overlap with position weighting
        words1 = str1.split()
        words2 = str2.split()
        
        if not words1 or not words2:
            return 0.0
            
        # Calculate word overlap
        common_words = set(words1).intersection(set(words2))
        if not common_words:
            return 0.0
            
        # Position-weighted similarity
        weighted_score = 0
        for word in common_words:
            pos1 = words1.index(word) / len(words1)
            pos2 = words2.index(word) / len(words2)
            position_similarity = 1 - abs(pos1 - pos2)
            weighted_score += position_similarity
            
        position_score = weighted_score / len(common_words)
        
        # Combine word overlap and position scores
        overlap_score = len(common_words) / max(len(words1), len(words2))
        final_score = (overlap_score * 0.7) + (position_score * 0.3)
        
        return min(0.95, final_score)  # Cap at 0.95 to differentiate from exact matches
        
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
            
            # Get all transactions for this user to use with ERF
            try:
                historical_transactions = Transaction.query.filter_by(
                    user_id=user_id
                ).order_by(Transaction.date.desc()).limit(100).all()
                
                # Initialize ERF processor
                erf_processor = ERFProcessor()
                
                # Process similar transactions
                success, message, similar_transactions = erf_processor.find_similar_transactions(
                    description,
                    [t.to_dict() for t in historical_transactions],
                    user_id
                )
                
                if not success:
                    self.logger.warning(f"ERF processing warning: {message}")
                    
            except Exception as e:
                self.logger.error(f"Error in ERF processing: {str(e)}")
                historical_transactions = []

            # Apply ERF to find similar transactions
            similar_trans = find_similar_transactions(description, historical_transactions)
            
            # Get account data for ASF
            account_data = [
                {
                    'id': acc.id,
                    'name': acc.name,
                    'category': acc.category,
                    'link': getattr(acc, 'link', None)
                }
                for acc in accounts
            ]

            results = {
                'pattern_matches': pattern_matches,
                'keyword_matches': keyword_matches,
                'rule_matches': rule_matches,
                'ai_suggestions': []
            }

            # Use AI features if enabled and confidence thresholds aren't met
            best_confidence = max(
                ([p['confidence'] for p in pattern_matches] +
                 [r['confidence'] for r in rule_matches] +
                 [0.0]),
                default=0.0
            )

            if best_confidence < AI_FEATURES_CONFIG['ERF']['text_threshold']:
                # ERF: Get explanation from similar transactions
                erf_explanation = None
                if AI_FEATURES_CONFIG['ERF']['enabled'] and similar_trans:
                    best_match = max(similar_trans, key=lambda x: x['similarity'])
                    if best_match['similarity'] >= AI_FEATURES_CONFIG['ERF']['text_threshold']:
                        erf_explanation = best_match['transaction'].explanation

                # ASF: Get account suggestions
                asf_account = None
                if AI_FEATURES_CONFIG['ASF']['enabled']:
                    asf_account = predict_account(description, erf_explanation or '', account_data)

                # ESF: Get explanation suggestions
                esf_explanation = None
                if AI_FEATURES_CONFIG['ESF']['enabled']:
                    esf_explanation = suggest_explanation(description, similar_trans) or erf_explanation

                # Combine AI suggestions
                results['ai_suggestions'] = [{
                    'account_suggestion': asf_account,
                    'explanation_suggestion': esf_explanation or erf_explanation,
                    'confidence': max(
                        [x['similarity'] for x in similar_trans] + [AI_FEATURES_CONFIG['ASF']['confidence_threshold']]
                    ),
                    'source': 'ai',
                    'features_used': {
                        'ERF': bool(erf_explanation),
                        'ASF': bool(asf_account),
                        'ESF': bool(esf_explanation)
                    }
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

# AI Feature Configuration
AI_FEATURES_CONFIG = {
    'ERF': {
        'enabled': True,
        'text_threshold': 0.8,
        'semantic_threshold': 0.7,
        'max_matches': 5
    },
    'ASF': {
        'enabled': True,
        'confidence_threshold': 0.7,
        'max_suggestions': 3
    },
    'ESF': {
        'enabled': True,
        'suggestion_limit': 5,
        'context_window': 10
    }
}

# Constants for similarity thresholds
TEXT_THRESHOLD = AI_FEATURES_CONFIG['ERF']['text_threshold']
SEMANTIC_THRESHOLD = AI_FEATURES_CONFIG['ERF']['semantic_threshold']
