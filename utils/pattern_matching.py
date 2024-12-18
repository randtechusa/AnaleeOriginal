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
            'statistical_metrics': {},
            'recurring_patterns': defaultdict(list),
            'periodicity_analysis': defaultdict(dict),
            'advanced_metrics': defaultdict(dict),
            'pattern_confidence': defaultdict(float),
            'seasonality_analysis': defaultdict(list)
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
                # Basic statistical metrics
                pattern_analysis['statistical_metrics'][desc] = {
                    'mean': sum(amounts) / len(amounts),
                    'variance': sum((x - (sum(amounts) / len(amounts))) ** 2 for x in amounts) / len(amounts),
                    'frequency': len(temporal_data),
                    'date_range': {
                        'first': min(t['date'] for t in temporal_data),
                        'last': max(t['date'] for t in temporal_data)
                    }
                }
                
                # Analyze recurring patterns
                recurring_analysis = self.analyze_recurring_patterns(temporal_data)
                if recurring_analysis['is_recurring']:
                    pattern_analysis['recurring_patterns'][desc].append(recurring_analysis)
                    
                # Analyze temporal stability
                dates = [t['date'] for t in temporal_data]
                stability_analysis = self.analyze_temporal_stability(amounts, dates)
                pattern_analysis['periodicity_analysis'][desc] = stability_analysis
                
                # Calculate advanced metrics
                advanced_metrics = self.calculate_advanced_metrics(amounts, dates)
                pattern_analysis['advanced_metrics'][desc] = advanced_metrics
                pattern_analysis['pattern_confidence'][desc] = advanced_metrics['reliability_score']
                
                # Analyze seasonality if enough data points
                if len(temporal_data) >= 4:
                    seasonality_score = self._detect_seasonality(amounts, dates)
                    pattern_analysis['seasonality_analysis'][desc] = {
                        'score': seasonality_score,
                        'dates': dates,
                        'amounts': amounts
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
            
            if desc:
                pattern = frequency_patterns[desc]
                pattern['count'] += 1
                if amount is not None:
                    pattern['amounts'].append(amount)
                if date:
                    pattern['dates'].append(date)
                if account:
                    pattern['accounts'].add(account)
                
        # Calculate frequency metrics
        patterns = {}
        for desc, data in frequency_patterns.items():
            if data['count'] >= 2:  # Only consider repeated transactions
                patterns[desc] = {
                    'frequency': data['count'],
                    'amount_stats': {
                        'min': min(data['amounts']) if data['amounts'] else 0,
                        'max': max(data['amounts']) if data['amounts'] else 0,
                        'avg': sum(data['amounts']) / len(data['amounts']) if data['amounts'] else 0
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
        
    def analyze_recurring_patterns(self, temporal_data: List[Dict]) -> Dict:
        """Analyze recurring patterns in temporal transaction data"""
        if not temporal_data or len(temporal_data) < 2:
            return {'is_recurring': False, 'confidence': 0.0}
            
        # Sort transactions by date
        sorted_data = sorted(temporal_data, key=lambda x: x['date'])
        
        # Calculate time intervals between transactions
        intervals = []
        for i in range(1, len(sorted_data)):
            interval = (sorted_data[i]['date'] - sorted_data[i-1]['date']).days
            intervals.append(interval)
            
        if not intervals:
            return {'is_recurring': False, 'confidence': 0.0}
            
        # Analyze interval patterns
        avg_interval = sum(intervals) / len(intervals)
        variance = sum((x - avg_interval) ** 2 for x in intervals) / len(intervals)
        std_dev = variance ** 0.5
        
        # Calculate coefficient of variation (CV) to measure regularity
        cv = std_dev / avg_interval if avg_interval > 0 else float('inf')
        
        # Determine if pattern is recurring based on CV
        is_recurring = cv < 0.5  # Less variation suggests more regular pattern
        
        # Calculate confidence based on regularity and sample size
        base_confidence = max(0, 1 - cv) if cv < 1 else 0
        sample_size_factor = min(len(intervals) / 6, 1)  # More samples increase confidence
        confidence = base_confidence * sample_size_factor
        
        return {
            'is_recurring': is_recurring,
            'confidence': confidence,
            'metrics': {
                'average_interval': avg_interval,
                'variance': variance,
                'coefficient_variation': cv,
                'sample_size': len(intervals)
            },
            'suggested_frequency': self._suggest_frequency(avg_interval)
        }
        
    def _suggest_frequency(self, avg_interval: float) -> str:
        """Suggest transaction frequency based on average interval"""
        if avg_interval < 2:
            return 'daily'
        elif avg_interval < 8:
            return 'weekly'
        elif avg_interval < 15:
            return 'biweekly'
        elif avg_interval < 32:
            return 'monthly'
        elif avg_interval < 95:
            return 'quarterly'
        else:
            return 'annually'
            
    def analyze_temporal_stability(self, amounts: List[float], dates: List[datetime]) -> Dict:
        """Analyze the stability of transaction amounts over time"""
        if not amounts or not dates or len(amounts) != len(dates):
            return {'stability': 0.0, 'trend': 'unknown'}
            
        # Sort by date
        amount_date_pairs = sorted(zip(dates, amounts), key=lambda x: x[0])
        sorted_amounts = [pair[1] for pair in amount_date_pairs]
        
        # Calculate trend
        if len(sorted_amounts) >= 2:
            trend_direction = sorted_amounts[-1] - sorted_amounts[0]
            if abs(trend_direction) < 0.01 * sorted_amounts[0]:
                trend = 'stable'
            else:
                trend = 'increasing' if trend_direction > 0 else 'decreasing'
        else:
            trend = 'unknown'
            
        # Calculate stability score
        if len(sorted_amounts) >= 2:
            avg = sum(sorted_amounts) / len(sorted_amounts)
            relative_variations = [abs(x - avg) / avg for x in sorted_amounts]
            stability_score = 1 - min(1, sum(relative_variations) / len(relative_variations))
        else:
            stability_score = 0.0
            
        return {
            'stability': stability_score,
            'trend': trend,
            'metrics': {
                'min_amount': min(sorted_amounts),
                'max_amount': max(sorted_amounts),
                'avg_amount': sum(sorted_amounts) / len(sorted_amounts)
            }
        }
    def calculate_advanced_metrics(self, amounts: List[float], dates: List[datetime]) -> Dict:
        """Calculate advanced statistical metrics for transaction patterns"""
        if not amounts or not dates or len(amounts) != len(dates):
            return {
                'seasonality_score': 0.0,
                'trend_strength': 0.0,
                'pattern_strength': 0.0,
                'reliability_score': 0.0
            }
            
        try:
            # Sort by date for time-series analysis
            amount_date_pairs = sorted(zip(dates, amounts), key=lambda x: x[0])
            sorted_amounts = [pair[1] for pair in amount_date_pairs]
            sorted_dates = [pair[0] for pair in amount_date_pairs]
            
            # Calculate basic stats
            mean_amount = sum(sorted_amounts) / len(sorted_amounts)
            deviations = [x - mean_amount for x in sorted_amounts]
            variance = sum(d * d for d in deviations) / len(deviations)
            std_dev = variance ** 0.5 if variance > 0 else 0
            
            # Calculate trend strength using linear regression approximation
            n = len(sorted_amounts)
            if n >= 2:
                x = list(range(n))
                x_mean = sum(x) / n
                y_mean = mean_amount
                
                # Calculate slope using least squares
                numerator = sum((x[i] - x_mean) * (sorted_amounts[i] - y_mean) for i in range(n))
                denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
                slope = numerator / denominator if denominator != 0 else 0
                
                # Normalize trend strength to [0, 1]
                trend_strength = min(abs(slope) / (mean_amount + 1e-6), 1.0)
            else:
                trend_strength = 0.0
                
            # Calculate pattern strength based on regularity
            if std_dev > 0:
                pattern_strength = 1.0 - min(std_dev / mean_amount, 1.0)
            else:
                pattern_strength = 1.0 if len(sorted_amounts) > 1 else 0.0
                
            # Calculate seasonality score
            seasonality_score = self._detect_seasonality(sorted_amounts, sorted_dates)
            
            # Calculate overall reliability score
            sample_size_factor = min(len(sorted_amounts) / 12, 1.0)  # More samples increase reliability
            time_span_factor = min((sorted_dates[-1] - sorted_dates[0]).days / 365, 1.0)
            reliability_score = (sample_size_factor * 0.4 + 
                              pattern_strength * 0.3 +
                              (1 - trend_strength) * 0.2 +  # Less trend means more stable pattern
                              seasonality_score * 0.1)
            
            return {
                'seasonality_score': seasonality_score,
                'trend_strength': trend_strength,
                'pattern_strength': pattern_strength,
                'reliability_score': reliability_score,
                'metrics': {
                    'mean': mean_amount,
                    'std_dev': std_dev,
                    'sample_size': len(sorted_amounts),
                    'date_range': {
                        'start': sorted_dates[0],
                        'end': sorted_dates[-1]
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating advanced metrics: {str(e)}")
            return {
                'seasonality_score': 0.0,
                'trend_strength': 0.0,
                'pattern_strength': 0.0,
                'reliability_score': 0.0
            }
            
    def _detect_seasonality(self, amounts: List[float], dates: List[datetime]) -> float:
        """Detect seasonal patterns in transaction amounts"""
        if len(amounts) < 4:  # Need at least 4 points to detect seasonality
            return 0.0
            
        try:
            # Calculate intervals between transactions
            intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
            
            if not intervals:
                return 0.0
                
            # Calculate average interval
            avg_interval = sum(intervals) / len(intervals)
            
            # Group transactions by similar intervals
            interval_groups = defaultdict(list)
            for i, interval in enumerate(intervals):
                normalized_interval = round(interval / avg_interval) * avg_interval
                interval_groups[normalized_interval].append(amounts[i])
                
            # Calculate seasonality score based on pattern regularity
            if len(interval_groups) > 1:
                group_sizes = [len(group) for group in interval_groups.values()]
                max_group_size = max(group_sizes)
                total_points = sum(group_sizes)
                
                # More regular grouping indicates stronger seasonality
                seasonality_score = max_group_size / total_points
            else:
                seasonality_score = 0.0
                
            return seasonality_score
            
        except Exception as e:
            logger.error(f"Error detecting seasonality: {str(e)}")
            return 0.0