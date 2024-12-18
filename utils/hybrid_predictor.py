from typing import List, Dict, Optional, Tuple
import logging
from .pattern_matching import PatternMatcher
from .keyword_matcher import KeywordMatcher
from ai_utils import predict_account, calculate_text_similarity
import time

logger = logging.getLogger(__name__)

class HybridPredictor:
    def __init__(self):
        self.pattern_matcher = PatternMatcher()
        self.keyword_matcher = KeywordMatcher()
        self.confidence_threshold = 0.85
        self.use_ai_threshold = 0.7
        self._initialize_keyword_rules()
        
    def _initialize_keyword_rules(self):
        """Initialize basic keyword rules for common categories"""
        # These are just examples - actual rules should be loaded from configuration
        common_rules = {
            'Utilities': ['electricity', 'water', 'gas', 'utility'],
            'Office Supplies': ['supplies', 'paper', 'toner', 'printer'],
            'Travel': ['flight', 'hotel', 'taxi', 'uber'],
            'Maintenance': ['repair', 'maintenance', 'cleaning'],
        }
        
        for category, keywords in common_rules.items():
            for keyword in keywords:
                self.keyword_matcher.add_keyword_rule(keyword, category)
                
    def get_keyword_suggestions(self, description: str) -> List[Dict]:
        """Get suggestions based on keyword matching"""
        try:
            return self.keyword_matcher.suggest_categories(description)
        except Exception as e:
            logger.error(f"Error in keyword matching: {str(e)}")
            return []

    async def get_suggestions(self, 
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
            # Start with pattern matching
            pattern_suggestions = self.pattern_matcher.suggest_from_patterns(
                description, amount, historical_data
            )
            
            # Get keyword-based suggestions
            keyword_suggestions = self.get_keyword_suggestions(description)
            
            combined = []
            
            # Add pattern-based suggestions
            for suggestion in pattern_suggestions:
                suggestion['source'] = 'pattern'
                combined.append(suggestion)
                
            # Add keyword-based suggestions
            for suggestion in keyword_suggestions:
                combined.append({
                    'confidence': suggestion['confidence'],
                    'category': suggestion['category'],
                    'match_type': suggestion['match_type'],
                    'source': 'keyword'
                })
            
            # Check if we need AI suggestions
            best_confidence = max((s.get('confidence', 0) for s in combined), default=0)
            
            if best_confidence < self.use_ai_threshold:
                # Get AI suggestions
                try:
                    ai_suggestions = await predict_account(description, "", available_accounts)
                    for ai_suggestion in ai_suggestions:
                        combined.append({
                            'confidence': ai_suggestion['confidence'],
                            'account_name': ai_suggestion['account_name'],
                            'account': ai_suggestion['account'],
                            'reasoning': ai_suggestion['reasoning'],
                            'source': 'ai'
                        })
                except Exception as ai_error:
                    logger.error(f"Error getting AI suggestions: {str(ai_error)}")
            
            # Sort by confidence and return top suggestions
            combined.sort(key=lambda x: x.get('confidence', 0), reverse=True)
            return combined[:3]
            
        except Exception as e:
            logger.error(f"Error in hybrid prediction: {str(e)}")
            return []