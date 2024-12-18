import re
from typing import List, Dict, Optional, Tuple
from Levenshtein import distance
import logging
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger(__name__)

class PatternMatcher:
    def __init__(self):
        self.exact_matches_cache = {}
        self.fuzzy_matches_cache = {}
        self.keyword_rules = defaultdict(list)
        self.min_similarity_score = 0.85
        
    def preprocess_description(self, description: str) -> str:
        """Standardize transaction description for matching"""
        if not description:
            return ""
        # Convert to lowercase and remove extra spaces
        processed = description.lower().strip()
        # Remove special characters but keep spaces
        processed = re.sub(r'[^\w\s]', '', processed)
        # Remove multiple spaces
        processed = re.sub(r'\s+', ' ', processed)
        return processed
        
    def calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity score between two strings"""
        if not str1 or not str2:
            return 0.0
        # Use Levenshtein distance for similarity
        max_len = max(len(str1), len(str2))
        if max_len == 0:
            return 1.0
        return 1 - (distance(str1, str2) / max_len)
        
    def find_exact_matches(self, description: str, historical_data: List[Dict]) -> List[Dict]:
        """Find exact matches in historical transactions"""
        processed_desc = self.preprocess_description(description)
        
        matches = []
        for transaction in historical_data:
            if self.preprocess_description(transaction['description']) == processed_desc:
                matches.append({
                    'confidence': 1.0,
                    'match_type': 'exact',
                    'transaction': transaction
                })
                
        return matches
        
    def find_fuzzy_matches(self, description: str, historical_data: List[Dict]) -> List[Dict]:
        """Find similar transactions using fuzzy matching"""
        processed_desc = self.preprocess_description(description)
        
        matches = []
        for transaction in historical_data:
            processed_hist = self.preprocess_description(transaction['description'])
            similarity = self.calculate_similarity(processed_desc, processed_hist)
            
            if similarity >= self.min_similarity_score:
                matches.append({
                    'confidence': similarity,
                    'match_type': 'fuzzy',
                    'transaction': transaction
                })
                
        return sorted(matches, key=lambda x: x['confidence'], reverse=True)[:5]
        
    def analyze_patterns(self, transactions: List[Dict]) -> Dict:
        """Analyze transaction patterns for common explanations and accounts"""
        pattern_analysis = {
            'frequent_explanations': defaultdict(int),
            'amount_patterns': defaultdict(list),
            'account_patterns': defaultdict(list)
        }
        
        for transaction in transactions:
            desc = self.preprocess_description(transaction.get('description', ''))
            explanation = transaction.get('explanation')
            amount = transaction.get('amount')
            account = transaction.get('account_name')
            
            if explanation:
                pattern_analysis['frequent_explanations'][explanation] += 1
                
            if amount and account:
                key = f"{desc}_{account}"
                pattern_analysis['amount_patterns'][key].append(amount)
                pattern_analysis['account_patterns'][key].append(account)
                
        return pattern_analysis
        
    def suggest_from_patterns(self, 
                            description: str, 
                            amount: float, 
                            historical_data: List[Dict]) -> List[Dict]:
        """Generate suggestions based on pattern analysis"""
        suggestions = []
        
        # Look for exact matches first
        exact_matches = self.find_exact_matches(description, historical_data)
        if exact_matches:
            suggestions.extend(exact_matches)
            
        # If no exact matches, try fuzzy matching
        if not exact_matches:
            fuzzy_matches = self.find_fuzzy_matches(description, historical_data)
            suggestions.extend(fuzzy_matches)
            
        # Analyze patterns in the matches
        if suggestions:
            pattern_analysis = self.analyze_patterns([m['transaction'] for m in suggestions])
            
            # Enhance suggestions with pattern analysis
            for suggestion in suggestions:
                transaction = suggestion['transaction']
                desc_key = self.preprocess_description(transaction.get('description', ''))
                account_key = f"{desc_key}_{transaction.get('account_name', '')}"
                
                # Add frequency information
                suggestion['frequency'] = pattern_analysis['frequent_explanations'].get(
                    transaction.get('explanation', ''), 0
                )
                
                # Add amount pattern information
                amount_patterns = pattern_analysis['amount_patterns'].get(account_key, [])
                if amount_patterns:
                    suggestion['amount_pattern'] = {
                        'min': min(amount_patterns),
                        'max': max(amount_patterns),
                        'avg': sum(amount_patterns) / len(amount_patterns)
                    }
                
        return suggestions

    def get_suggestion_confidence(self, suggestion: Dict) -> float:
        """Calculate overall confidence score for a suggestion"""
        base_confidence = suggestion.get('confidence', 0.0)
        
        # Adjust confidence based on frequency
        frequency_factor = min(suggestion.get('frequency', 0) / 10, 1.0)
        
        # Adjust confidence based on amount patterns
        amount_pattern = suggestion.get('amount_pattern', {})
        if amount_pattern:
            amount = suggestion['transaction'].get('amount', 0)
            if amount_pattern['min'] <= amount <= amount_pattern['max']:
                amount_factor = 0.2
            else:
                amount_factor = 0
        else:
            amount_factor = 0
            
        # Calculate weighted confidence
        final_confidence = (
            base_confidence * 0.6 +  # Base similarity
            frequency_factor * 0.3 +  # Usage frequency
            amount_factor * 0.1   # Amount pattern match
        )
        
        return min(final_confidence, 1.0)
