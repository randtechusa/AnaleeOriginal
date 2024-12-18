from typing import List, Dict, Optional
import logging
from .pattern_matching import PatternMatcher
from ai_utils import predict_account, calculate_text_similarity
import time

logger = logging.getLogger(__name__)

class HybridPredictor:
    def __init__(self):
        self.pattern_matcher = PatternMatcher()
        self.confidence_threshold = 0.85
        self.use_ai_threshold = 0.7
        
    async def get_suggestions(self, 
                            description: str,
                            amount: float,
                            historical_data: List[Dict],
                            available_accounts: List[Dict]) -> List[Dict]:
        """
        Get suggestions using both pattern matching and AI approaches
        """
        try:
            # Start with pattern-based matching (faster and cheaper)
            pattern_suggestions = self.pattern_matcher.suggest_from_patterns(
                description, amount, historical_data
            )
            
            # If pattern matching gives high-confidence results, use those
            high_confidence_suggestions = [
                s for s in pattern_suggestions 
                if self.pattern_matcher.get_suggestion_confidence(s) >= self.confidence_threshold
            ]
            
            if high_confidence_suggestions:
                logger.info("Using high-confidence pattern-based suggestions")
                return high_confidence_suggestions
                
            # If pattern matching confidence is moderate, combine with AI
            moderate_confidence = any(
                self.pattern_matcher.get_suggestion_confidence(s) >= self.use_ai_threshold
                for s in pattern_suggestions
            )
            
            if moderate_confidence:
                # Get AI suggestions
                ai_suggestions = await self._get_ai_suggestions(
                    description, amount, available_accounts
                )
                
                # Combine and rank suggestions
                return self._combine_suggestions(
                    pattern_suggestions, ai_suggestions
                )
                
            # If pattern matching confidence is low, rely on AI
            logger.info("Using AI-based suggestions due to low pattern confidence")
            return await self._get_ai_suggestions(
                description, amount, available_accounts
            )
            
        except Exception as e:
            logger.error(f"Error in hybrid prediction: {str(e)}")
            # Fallback to pattern-based suggestions in case of AI errors
            return pattern_suggestions if pattern_suggestions else []
            
    async def _get_ai_suggestions(self,
                                description: str,
                                amount: float,
                                available_accounts: List[Dict]) -> List[Dict]:
        """Get suggestions using AI"""
        try:
            ai_predictions = predict_account(
                description=description,
                explanation="",  # We don't have an explanation yet
                available_accounts=available_accounts
            )
            
            return [
                {
                    'confidence': pred['confidence'],
                    'match_type': 'ai',
                    'account': pred['account'],
                    'reasoning': pred['reasoning']
                }
                for pred in ai_predictions
            ]
            
        except Exception as e:
            logger.error(f"Error getting AI suggestions: {str(e)}")
            return []
            
    def _combine_suggestions(self,
                           pattern_suggestions: List[Dict],
                           ai_suggestions: List[Dict]) -> List[Dict]:
        """Combine and rank suggestions from both approaches"""
        combined = []
        
        # Process pattern-based suggestions
        for p_suggestion in pattern_suggestions:
            p_confidence = self.pattern_matcher.get_suggestion_confidence(p_suggestion)
            combined.append({
                'confidence': p_confidence,
                'match_type': 'hybrid_pattern',
                'account': p_suggestion['transaction']['account'],
                'reasoning': f"Based on historical pattern matching (confidence: {p_confidence:.2f})",
                'source': 'pattern'
            })
            
        # Process AI suggestions
        for ai_suggestion in ai_suggestions:
            combined.append({
                'confidence': ai_suggestion['confidence'],
                'match_type': 'hybrid_ai',
                'account': ai_suggestion['account'],
                'reasoning': ai_suggestion['reasoning'],
                'source': 'ai'
            })
            
        # Sort by confidence and return top suggestions
        return sorted(combined, key=lambda x: x['confidence'], reverse=True)[:3]
