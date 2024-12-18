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
        try:
            # Convert to lowercase and remove extra spaces
            processed = description.lower().strip()
            # Remove common prefixes/suffixes that don't affect meaning
            processed = re.sub(r'^(payment to |payment from |trans to |trans from )', '', processed)
            # Remove special characters but keep spaces
            processed = re.sub(r'[^\w\s-]', '', processed)
            # Standardize spaces
            processed = re.sub(r'\s+', ' ', processed)
            # Remove trailing numbers (often reference numbers)
            processed = re.sub(r'\s+\d+$', '', processed)
            logger.debug(f"Preprocessed description: '{description}' -> '{processed}'")
            return processed
        except Exception as e:
            logger.error(f"Error preprocessing description '{description}': {str(e)}")
            return description.lower().strip()
        
    def calculate_similarity(self, str1: str, str2: str) -> float:
        """
        Calculate similarity score between two strings using enhanced Levenshtein distance
        with length normalization and preprocessing
        """
        if not str1 or not str2:
            return 0.0
            
        # Handle exact matches efficiently
        if str1 == str2:
            return 1.0
            
        # Length-based early filtering
        len1, len2 = len(str1), len(str2)
        max_len = max(len1, len2)
        min_len = min(len1, len2)
        
        # If length difference is too large, strings are likely very different
        if max_len == 0 or min_len / max_len < 0.5:
            return 0.0
            
        # Calculate normalized Levenshtein distance
        leven_dist = distance(str1, str2)
        similarity = 1 - (leven_dist / max_len)
        
        # Apply length difference penalty
        length_similarity = min_len / max_len
        final_similarity = similarity * (0.8 + 0.2 * length_similarity)
        
        return max(0.0, min(1.0, final_similarity))
        
    def find_exact_matches(self, description: str, historical_data: List[Dict]) -> List[Dict]:
        """Find exact matches in historical transactions"""
        try:
            processed_desc = self.preprocess_description(description)
            if not processed_desc:
                logger.warning("Empty description after preprocessing")
                return []

            matches = []
            match_count = 0
            
            for transaction in historical_data:
                hist_desc = self.preprocess_description(transaction.get('description', ''))
                if hist_desc == processed_desc:
                    match_count += 1
                    confidence = 1.0
                    
                    # Adjust confidence based on frequency and amount similarity
                    if 'amount' in transaction:
                        matches.append({
                            'confidence': confidence,
                            'match_type': 'exact',
                            'transaction': transaction,
                            'match_details': {
                                'preprocessed_description': processed_desc,
                                'original_description': description,
                                'matched_description': transaction.get('description', ''),
                                'frequency': match_count
                            }
                        })
                    
            if matches:
                logger.info(f"Found {len(matches)} exact matches for description '{description}'")
            else:
                logger.debug(f"No exact matches found for description '{description}'")
                
            return sorted(matches, key=lambda x: (x['confidence'], x['match_details']['frequency']), reverse=True)
            
        except Exception as e:
            logger.error(f"Error finding exact matches for '{description}': {str(e)}")
            return []
        
    def find_fuzzy_matches(self, description: str, historical_data: List[Dict]) -> List[Dict]:
        """
        Find similar transactions using enhanced fuzzy matching with detailed metadata
        """
        processed_desc = self.preprocess_description(description)
        if not processed_desc:
            return []
            
        matches = []
        for transaction in historical_data:
            processed_hist = self.preprocess_description(transaction.get('description', ''))
            similarity = self.calculate_similarity(processed_desc, processed_hist)
            
            if similarity >= self.min_similarity_score:
                # Calculate additional confidence factors
                amount_similarity = 1.0
                if 'amount' in transaction:
                    amount_similarity = self._calculate_amount_similarity(
                        transaction.get('amount', 0),
                        [t.get('amount', 0) for t in historical_data if t.get('description') == transaction.get('description')]
                    )
                
                matches.append({
                    'confidence': similarity,
                    'match_type': 'fuzzy',
                    'transaction': transaction,
                    'match_metadata': {
                        'similarity_score': similarity,
                        'processed_description': processed_desc,
                        'matched_description': processed_hist,
                        'amount_similarity': amount_similarity,
                        'combined_score': (similarity * 0.7 + amount_similarity * 0.3)
                    }
                })
                
        # Sort by combined score and confidence
        matches.sort(key=lambda x: (
            x['match_metadata']['combined_score'],
            x['confidence']
        ), reverse=True)
        
        return matches[:5]
        
    def _calculate_amount_similarity(self, amount: float, historical_amounts: List[float]) -> float:
        """Calculate similarity score based on transaction amounts"""
        if not historical_amounts or amount == 0:
            return 0.5  # Neutral score when no historical data
            
        mean_amount = sum(historical_amounts) / len(historical_amounts)
        if mean_amount == 0:
            return 0.5
            
        # Calculate normalized difference
        diff_ratio = abs(amount - mean_amount) / max(abs(mean_amount), abs(amount))
        similarity = 1 - min(diff_ratio, 1.0)
        
        return similarity
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
        try:
            suggestions = []
            processed_desc = self.preprocess_description(description)
            
            if not processed_desc:
                logger.warning("Empty description, cannot generate suggestions")
                return []
            
            # Get frequency patterns first for efficiency
            frequency_patterns = self.analyze_frequency_patterns(historical_data)
            freq_match = frequency_patterns.get(processed_desc, {})
            
            # Get amount patterns
            amount_patterns = self.detect_amount_patterns(
                {'description': description, 'amount': amount},
                historical_data
            )
            
            # Look for exact matches first - highest confidence
            exact_matches = self.find_exact_matches(description, historical_data)
            if exact_matches:
                for match in exact_matches:
                    # Enhanced confidence scoring for exact matches
                    frequency_boost = min(0.1, freq_match.get('confidence', 0) * 0.2)
                    amount_confidence = amount_patterns['confidence']
                    
                    match['pattern_confidence'] = {
                        'exact_match': 1.0,
                        'frequency': freq_match.get('confidence', 0),
                        'amount': amount_confidence,
                        'reliability_score': 0.95 + frequency_boost  # High base reliability for exact matches
                    }
                    
                    # Add match metadata
                    match['match_metadata'] = {
                        'match_type': 'exact',
                        'frequency_data': freq_match,
                        'amount_pattern': amount_patterns.get('patterns', {}),
                        'processed_description': processed_desc
                    }
                suggestions.extend(exact_matches)
                logger.info(f"Found {len(exact_matches)} exact matches with high confidence")
                
            # If no exact matches, try fuzzy matching
            if not exact_matches:
                fuzzy_matches = self.find_fuzzy_matches(description, historical_data)
                for match in fuzzy_matches:
                    # Calculate fuzzy match confidence
                    base_confidence = match['confidence']
                    frequency_factor = freq_match.get('confidence', 0) * 0.3
                    amount_factor = amount_patterns['confidence'] * 0.3
                    
                    match['pattern_confidence'] = {
                        'fuzzy_match': base_confidence,
                        'frequency': frequency_factor,
                        'amount': amount_factor,
                        'reliability_score': (base_confidence * 0.6 + 
                                           frequency_factor * 0.25 + 
                                           amount_factor * 0.15)
                    }
                    
                    # Add match metadata
                    match['match_metadata'] = {
                        'match_type': 'fuzzy',
                        'similarity_score': base_confidence,
                        'frequency_data': freq_match,
                        'amount_pattern': amount_patterns.get('patterns', {}),
                        'processed_description': processed_desc
                    }
                suggestions.extend(fuzzy_matches)
                
            # Enhance suggestions with pattern analysis
            if suggestions:
                pattern_analysis = self.analyze_patterns([m['transaction'] for m in suggestions])
                
                for suggestion in suggestions:
                    transaction = suggestion['transaction']
                    desc_key = self.preprocess_description(transaction.get('description', ''))
                    account_key = f"{desc_key}_{transaction.get('account_name', '')}"
                    
                    # Add enhanced frequency information
                    freq_info = pattern_analysis['frequent_explanations'].get(
                        transaction.get('explanation', ''), 0
                    )
                    suggestion['frequency_analysis'] = {
                        'count': freq_info,
                        'confidence_boost': min(0.15, freq_info / 10)  # Cap at 0.15
                    }
                    
                    # Enhanced amount pattern analysis
                    amount_patterns = pattern_analysis['amount_patterns'].get(account_key, [])
                    if amount_patterns:
                        avg_amount = sum(amount_patterns) / len(amount_patterns)
                        suggestion['amount_analysis'] = {
                            'min': min(amount_patterns),
                            'max': max(amount_patterns),
                            'avg': avg_amount,
                            'variance': sum((x - avg_amount) ** 2 for x in amount_patterns) / len(amount_patterns)
                        }
                    
                    # Calculate final weighted confidence score
                    pattern_conf = suggestion['pattern_confidence']
                    base_score = pattern_conf.get('exact_match', pattern_conf.get('fuzzy_match', 0))
                    freq_score = suggestion['frequency_analysis']['confidence_boost']
                    amount_score = pattern_conf.get('amount', 0)
                    reliability = pattern_conf.get('reliability_score', 0)
                    
                    suggestion['confidence'] = min(1.0, (
                        base_score * 0.4 +
                        freq_score * 0.3 +
                        amount_score * 0.2 +
                        reliability * 0.1
                    ))
                    
                # Sort by confidence and limit results
                suggestions.sort(key=lambda x: x['confidence'], reverse=True)
                logger.info(f"Generated {len(suggestions)} total suggestions, sorted by confidence")
                return suggestions[:5]  # Return top 5 suggestions
                
        except Exception as e:
            logger.error(f"Error generating pattern suggestions: {str(e)}")
            return []
            
        return []  # Fallback empty return

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
        # Initialize with proper typing for collections
        frequency_patterns: Dict[str, Dict] = {}
        
        for transaction in transactions:
            desc = self.preprocess_description(transaction.get('description', ''))
            amount = transaction.get('amount', 0)
            date = transaction.get('date')
            account = transaction.get('account_name')
            
            if desc:
                if desc not in frequency_patterns:
                    frequency_patterns[desc] = {
                        'count': 0,
                        'amounts': [],
                        'dates': [],
                        'accounts': set()
                    }
                pattern = frequency_patterns[desc]
                pattern['count'] = pattern['count'] + 1
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
        """Calculate advanced statistical metrics for transaction patterns with enhanced historical analysis"""
        if not amounts or not dates or len(amounts) != len(dates):
            return {
                'seasonality_score': 0.0,
                'trend_strength': 0.0,
                'pattern_strength': 0.0,
                'reliability_score': 0.0,
                'historical_metrics': {}
            }
            
        try:
            # Sort by date for time-series analysis
            amount_date_pairs = sorted(zip(dates, amounts), key=lambda x: x[0])
            sorted_amounts = [pair[1] for pair in amount_date_pairs]
            sorted_dates = [pair[0] for pair in amount_date_pairs]
            
            # Calculate enhanced historical statistics
            mean_amount = sum(sorted_amounts) / len(sorted_amounts)
            deviations = [x - mean_amount for x in sorted_amounts]
            variance = sum(d * d for d in deviations) / len(deviations)
            std_dev = variance ** 0.5 if variance > 0 else 0
            
            # Calculate rolling statistics for trend detection
            window_size = min(3, len(sorted_amounts))
            rolling_means = []
            for i in range(len(sorted_amounts) - window_size + 1):
                window = sorted_amounts[i:i + window_size]
                rolling_means.append(sum(window) / len(window))
                
            # Calculate month-over-month changes
            monthly_changes = []
            if len(sorted_dates) >= 2:
                for i in range(1, len(sorted_dates)):
                    days_diff = (sorted_dates[i] - sorted_dates[i-1]).days
                    if 25 <= days_diff <= 35:  # Approximately monthly
                        change = (sorted_amounts[i] - sorted_amounts[i-1]) / sorted_amounts[i-1]
                        monthly_changes.append(change)
            
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
            
    def calculate_historical_confidence(self, transaction_data: List[Dict]) -> Dict:
        """Calculate confidence scores based on historical pattern analysis"""
        if not transaction_data:
            return {'confidence': 0.0, 'metrics': {}}
            
        try:
            # Extract relevant data
            amounts = [float(t.get('amount', 0)) for t in transaction_data]
            dates = [t.get('date') for t in transaction_data if t.get('date')]
            descriptions = [t.get('description', '') for t in transaction_data]
            
            # Initialize metrics
            metrics = {
                'transaction_count': len(transaction_data),
                'date_range': None,
                'amount_stability': 0.0,
                'frequency_score': 0.0,
                'pattern_confidence': 0.0,
                'interval_analysis': None,
                'amount_pattern': None
            }
            
            if dates:
                # Calculate date range and frequency
                first_date = min(dates)
                last_date = max(dates)
                date_range_days = (last_date - first_date).days
                
                if date_range_days > 0:
                    # Calculate transaction frequency score
                    avg_days_between = date_range_days / (len(dates) - 1) if len(dates) > 1 else float('inf')
                    metrics['frequency_score'] = min(1.0, 30 / avg_days_between) if avg_days_between > 0 else 0.0
                    
                metrics['date_range'] = {
                    'first': first_date.isoformat(),
                    'last': last_date.isoformat(),
                    'days': date_range_days
                }
            
            if amounts:
                # Calculate amount stability and patterns
                mean_amount = sum(amounts) / len(amounts)
                if len(amounts) > 1:
                    relative_std = statistics.stdev(amounts) / mean_amount
                    metrics['amount_stability'] = max(0.0, min(1.0, 1 - relative_std))
                    
                    # Group similar amounts
                    amount_groups = defaultdict(list)
                    for amount in amounts:
                        # Group amounts within 1% of each other
                        normalized_amount = round(amount / (mean_amount * 0.01)) * (mean_amount * 0.01)
                        amount_groups[normalized_amount].append(amount)
                    
                    # Analyze amount patterns
                    if amount_groups:
                        largest_group = max(amount_groups.values(), key=len)
                        amount_consistency = len(largest_group) / len(amounts)
                        metrics['amount_pattern'] = {
                            'consistency': amount_consistency,
                            'common_amount': round(sum(largest_group) / len(largest_group), 2),
                            'variation_count': len(amount_groups)
                        }
                
            # Calculate interval patterns
            if dates and len(dates) > 1:
                intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
                metrics['interval_analysis'] = self._detect_seasonality(intervals, amounts[1:])
                
                # Update frequency score based on interval analysis
                if metrics['interval_analysis']['interval_type']:
                    metrics['frequency_score'] = metrics['interval_analysis']['score']
            
            # Calculate overall pattern confidence with enhanced metrics
            metrics['pattern_confidence'] = (
                metrics['frequency_score'] * 0.35 +
                metrics['amount_stability'] * 0.35 +
                min(1.0, len(transaction_data) / 10) * 0.2 +  # Sample size factor
                (metrics['amount_pattern']['consistency'] if metrics.get('amount_pattern') else 0.0) * 0.1
            )
            
            return {
                'confidence': metrics['pattern_confidence'],
                'metrics': metrics
            }
            
        except Exception as e:
            logger.error(f"Error calculating historical confidence: {str(e)}")
            return {'confidence': 0.0, 'metrics': {}}

            if not intervals:
                return {'score': 0.0, 'interval_type': None}
                
            # Calculate average interval
            avg_interval = sum(intervals) / len(intervals)
            
            # Detect common interval patterns
            interval_types = {
                'daily': 1,
                'weekly': 7,
                'biweekly': 14,
                'monthly': 30,
                'quarterly': 90,
                'yearly': 365
            }
            
            # Group transactions by similar intervals
            interval_groups = defaultdict(list)
            interval_type_scores = defaultdict(float)
            
            for i, interval in enumerate(intervals):
                normalized_interval = round(interval / avg_interval) * avg_interval
                interval_groups[normalized_interval].append(amounts[i])
                
                # Score against known interval types
                for interval_name, days in interval_types.items():
                    similarity = 1 - min(abs(interval - days) / max(days, interval), 1)
                    interval_type_scores[interval_name] = max(
                        interval_type_scores[interval_name],
                        similarity
                    )
            
            # Find the most likely interval type
            best_interval_type = max(
                interval_type_scores.items(),
                key=lambda x: x[1]
            ) if interval_type_scores else (None, 0)
            
            # Calculate regularity score
            if len(interval_groups) > 1:
                group_sizes = [len(group) for group in interval_groups.values()]
                max_group_size = max(group_sizes)
                total_points = sum(group_sizes)
                regularity_score = max_group_size / total_points
            else:
                regularity_score = 0.0
            
            return {
                'score': regularity_score,
                'interval_type': best_interval_type[0],
                'confidence': best_interval_type[1],
                'avg_interval_days': round(avg_interval, 1),
                'pattern_metrics': {
                    name: round(score, 2)
                    for name, score in interval_type_scores.items()
                }
            }
            
        except Exception as e:
            logger.error(f"Error detecting seasonality: {str(e)}")
            return {'score': 0.0, 'interval_type': None, 'error': str(e)}