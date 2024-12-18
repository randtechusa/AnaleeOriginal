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
        """Enhanced analysis of transaction patterns including temporal and statistical patterns"""
        pattern_analysis = {
            'frequent_explanations': defaultdict(int),
            'amount_patterns': defaultdict(list),
            'account_patterns': defaultdict(list),
            'temporal_patterns': defaultdict(list),
            'statistical_metrics': {}
        }
        
        for transaction in transactions:
            desc = self.preprocess_description(transaction.get('description', ''))
            explanation = transaction.get('explanation')
            amount = transaction.get('amount')
            account = transaction.get('account_name')
            date = transaction.get('date')
            
            if explanation:
                pattern_analysis['frequent_explanations'][explanation] += 1
                
            if amount and account:
                key = f"{desc}_{account}"
                pattern_analysis['amount_patterns'][key].append(amount)
                pattern_analysis['account_patterns'][key].append(account)
                
            if date and amount:
                pattern_analysis['temporal_patterns'][desc].append({
                    'date': date,
                    'amount': amount,
                    'account': account
                })
        
        # Calculate statistical metrics for patterns
        for desc, temporal_data in pattern_analysis['temporal_patterns'].items():
            if len(temporal_data) >= 2:
                amounts = [t['amount'] for t in temporal_data]
                pattern_analysis['statistical_metrics'][desc] = {
                    'mean': sum(amounts) / len(amounts),
                    'variance': sum((x - (sum(amounts) / len(amounts))) ** 2 for x in amounts) / len(amounts),
                    'frequency': len(temporal_data),
                    'date_range': {
                        'first': min(t['date'] for t in temporal_data),
                        'last': max(t['date'] for t in temporal_data)
                    }
                }
                
        return pattern_analysis
        
    def suggest_from_patterns(self, 
                            description: str, 
                            amount: float, 
                            historical_data: List[Dict]) -> List[Dict]:
        """Generate suggestions based on comprehensive pattern analysis"""
        suggestions = []
        processed_desc = self.preprocess_description(description)
        
        # Get frequency patterns
        frequency_patterns = self.analyze_frequency_patterns(historical_data)
        freq_match = frequency_patterns.get(processed_desc, {})
        
        # Get amount patterns
        amount_patterns = self.detect_amount_patterns(
            {'description': description, 'amount': amount},
            historical_data
        )
        
        # Look for exact matches first
        exact_matches = self.find_exact_matches(description, historical_data)
        if exact_matches:
            for match in exact_matches:
                match['pattern_confidence'] = {
                    'exact_match': 1.0,
                    'frequency': freq_match.get('confidence', 0),
                    'amount': amount_patterns['confidence']
                }
            suggestions.extend(exact_matches)
            
        # If no exact matches, try fuzzy matching
        if not exact_matches:
            fuzzy_matches = self.find_fuzzy_matches(description, historical_data)
            for match in fuzzy_matches:
                match['pattern_confidence'] = {
                    'fuzzy_match': match['confidence'],
                    'frequency': freq_match.get('confidence', 0),
                    'amount': amount_patterns['confidence']
                }
            suggestions.extend(fuzzy_matches)
            
        # Enhance suggestions with pattern analysis
        if suggestions:
            pattern_analysis = self.analyze_patterns([m['transaction'] for m in suggestions])
            
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
                
                # Calculate weighted confidence score
                pattern_conf = suggestion['pattern_confidence']
                suggestion['confidence'] = (
                    pattern_conf.get('exact_match', pattern_conf.get('fuzzy_match', 0)) * 0.4 +
                    pattern_conf.get('frequency', 0) * 0.3 +
                    pattern_conf.get('amount', 0) * 0.3
                )
                
        return sorted(suggestions, key=lambda x: x['confidence'], reverse=True)

    def get_suggestion_confidence(self, suggestion: Dict) -> float:
        """Calculate enhanced confidence score incorporating statistical and temporal patterns"""
        base_confidence = suggestion.get('confidence', 0.0)
        
        # Get pattern confidence factors
        pattern_conf = suggestion.get('pattern_confidence', {})
        
        # Base pattern confidence (exact or fuzzy match)
        base_pattern = pattern_conf.get('exact_match', pattern_conf.get('fuzzy_match', 0))
        
        # Frequency confidence
        frequency_factor = min(suggestion.get('frequency', 0) / 10, 1.0)
        
        # Amount pattern confidence
        amount_pattern = suggestion.get('amount_pattern', {})
        amount_factor = 0
        if amount_pattern:
            amount = suggestion['transaction'].get('amount', 0)
            if amount_pattern['min'] <= amount <= amount_pattern['max']:
                # Calculate z-score based confidence
                mean = amount_pattern['avg']
                if 'std_dev' in suggestion:
                    std_dev = suggestion['std_dev']
                    if std_dev > 0:
                        z_score = abs(amount - mean) / std_dev
                        amount_factor = max(0, 1 - (z_score / 3))
                else:
                    # Fallback to range-based confidence
                    amount_factor = 0.2
        
        # Statistical pattern confidence
        statistical_factor = 0
        if 'statistical_metrics' in suggestion:
            stats = suggestion['statistical_metrics']
            if stats.get('frequency', 0) > 0:
                # More frequent patterns get higher confidence
                statistical_factor = min(stats['frequency'] / 5, 0.3)
                
                # Add variance-based confidence
                if stats.get('variance', float('inf')) > 0:
                    variance_factor = max(0, 1 - (stats['variance'] / 1000))  # Scale variance impact
                    statistical_factor += variance_factor * 0.2
        
        # Calculate weighted confidence
        final_confidence = (
            base_pattern * 0.3 +           # Base pattern match
            frequency_factor * 0.2 +       # Usage frequency
            amount_factor * 0.2 +          # Amount pattern match
            statistical_factor * 0.2 +     # Statistical patterns
            pattern_conf.get('temporal', 0) * 0.1  # Temporal patterns
        )
        
        return min(final_confidence, 1.0)
        
    def analyze_frequency_patterns(self, transactions: List[Dict]) -> Dict:
        """Analyze transaction frequency patterns"""
        frequency_patterns = defaultdict(lambda: {
            'count': 0,
            'amounts': [],
            'dates': [],
            'accounts': set()
        })
        
        for transaction in transactions:
            desc = self.preprocess_description(transaction.get('description', ''))
            amount = transaction.get('amount', 0)
            date = transaction.get('date')
            account = transaction.get('account_name')
            
            frequency_patterns[desc]['count'] += 1
            frequency_patterns[desc]['amounts'].append(amount)
            if date:
                frequency_patterns[desc]['dates'].append(date)
            if account:
                frequency_patterns[desc]['accounts'].add(account)
                
        # Calculate frequency metrics
        patterns = {}
        for desc, data in frequency_patterns.items():
            if data['count'] >= 2:  # Only consider repeated transactions
                patterns[desc] = {
                    'frequency': data['count'],
                    'amount_stats': {
                        'min': min(data['amounts']),
                        'max': max(data['amounts']),
                        'avg': sum(data['amounts']) / len(data['amounts'])
                    },
                    'accounts': list(data['accounts']),
                    'confidence': min(data['count'] / 10, 0.9)  # Cap at 0.9
                }
                
        return patterns
        
    def detect_amount_patterns(self, transaction: Dict, historical_data: List[Dict]) -> Dict:
        """Detect patterns in transaction amounts"""
        amount = transaction.get('amount', 0)
        description = self.preprocess_description(transaction.get('description', ''))
        
        # Group similar transactions
        similar_transactions = [
            t for t in historical_data
            if self.calculate_similarity(
                description,
                self.preprocess_description(t.get('description', ''))
            ) >= self.min_similarity_score
        ]
        
        if not similar_transactions:
            return {'confidence': 0, 'patterns': {}}
            
        amounts = [t.get('amount', 0) for t in similar_transactions]
        if not amounts:
            return {'confidence': 0, 'patterns': {}}
            
        # Calculate amount statistics
        avg_amount = sum(amounts) / len(amounts)
        std_dev = (sum((x - avg_amount) ** 2 for x in amounts) / len(amounts)) ** 0.5
        
        # Check if current amount fits the pattern
        amount_confidence = 0
        if std_dev > 0:
            z_score = abs(amount - avg_amount) / std_dev
            amount_confidence = max(0, 1 - (z_score / 3))  # Scale confidence based on z-score
            
        return {
            'confidence': amount_confidence,
            'patterns': {
                'average': avg_amount,
                'std_dev': std_dev,
                'count': len(amounts),
                'similar_amounts': sorted(amounts)[:5]  # Show up to 5 similar amounts
            }
        }
