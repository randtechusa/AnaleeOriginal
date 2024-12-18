from typing import List, Dict, Optional, Tuple
from collections import defaultdict
import logging
from datetime import datetime, timedelta
import statistics
from sqlalchemy import func
from models import db, Transaction, Account

logger = logging.getLogger(__name__)

class AccountUsageAnalyzer:
    """Analyzes statistical patterns in account usage"""
    
    def __init__(self):
        self.min_data_points = 3
        self.significance_threshold = 0.1  # 10% threshold for pattern significance
        
    def analyze_account_usage(self, account_id: int, 
                            start_date: Optional[datetime] = None,
                            end_date: Optional[datetime] = None) -> Dict:
        """
        Analyze usage patterns for a specific account
        Returns statistical metrics about account usage
        """
        try:
            # Query transactions for the account
            query = Transaction.query.filter_by(account_id=account_id)
            if start_date:
                query = query.filter(Transaction.transaction_date >= start_date)
            if end_date:
                query = query.filter(Transaction.transaction_date <= end_date)
                
            transactions = query.order_by(Transaction.transaction_date).all()
            
            if len(transactions) < self.min_data_points:
                return {
                    'status': 'insufficient_data',
                    'message': f'Need at least {self.min_data_points} transactions for analysis',
                    'transaction_count': len(transactions)
                }
                
            # Calculate basic statistics
            amounts = [float(t.amount) for t in transactions]
            dates = [t.transaction_date for t in transactions]
            
            basic_stats = self._calculate_basic_stats(amounts)
            temporal_patterns = self._analyze_temporal_patterns(dates, amounts)
            amount_patterns = self._analyze_amount_patterns(amounts)
            usage_frequency = self._analyze_usage_frequency(dates)
            
            # Combine all analyses
            analysis = {
                'status': 'success',
                'transaction_count': len(transactions),
                'date_range': {
                    'start': min(dates).isoformat(),
                    'end': max(dates).isoformat(),
                    'days': (max(dates) - min(dates)).days
                },
                'basic_statistics': basic_stats,
                'temporal_patterns': temporal_patterns,
                'amount_patterns': amount_patterns,
                'usage_frequency': usage_frequency,
                'confidence_score': self._calculate_confidence_score(
                    basic_stats, temporal_patterns, amount_patterns, usage_frequency
                )
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing account usage: {str(e)}")
            return {
                'status': 'error',
                'message': f'Analysis failed: {str(e)}'
            }
            
    def _calculate_basic_stats(self, amounts: List[float]) -> Dict:
        """Calculate basic statistical metrics"""
        try:
            return {
                'mean': statistics.mean(amounts),
                'median': statistics.median(amounts),
                'std_dev': statistics.stdev(amounts) if len(amounts) > 1 else 0,
                'min': min(amounts),
                'max': max(amounts),
                'total_volume': sum(amounts),
                'unique_amounts': len(set(amounts))
            }
        except Exception as e:
            logger.error(f"Error calculating basic stats: {str(e)}")
            return {}
            
    def _analyze_temporal_patterns(self, dates: List[datetime], 
                                 amounts: List[float]) -> Dict:
        """Analyze patterns in transaction timing"""
        try:
            # Calculate intervals between transactions
            intervals = [(dates[i+1] - dates[i]).days 
                        for i in range(len(dates)-1)]
            
            if not intervals:
                return {'pattern_detected': False}
                
            # Detect regular intervals
            interval_patterns = self._detect_interval_patterns(intervals)
            
            # Analyze daily/weekly/monthly patterns
            daily_pattern = self._analyze_daily_pattern(dates)
            weekly_pattern = self._analyze_weekly_pattern(dates)
            monthly_pattern = self._analyze_monthly_pattern(dates)
            
            return {
                'pattern_detected': any([
                    interval_patterns['pattern_detected'],
                    daily_pattern['pattern_detected'],
                    weekly_pattern['pattern_detected'],
                    monthly_pattern['pattern_detected']
                ]),
                'interval_patterns': interval_patterns,
                'daily_patterns': daily_pattern,
                'weekly_patterns': weekly_pattern,
                'monthly_patterns': monthly_pattern,
                'regularity_score': self._calculate_regularity_score(intervals)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing temporal patterns: {str(e)}")
            return {'pattern_detected': False}
            
    def _detect_interval_patterns(self, intervals: List[int]) -> Dict:
        """Detect patterns in transaction intervals"""
        if not intervals:
            return {'pattern_detected': False}
            
        try:
            # Group similar intervals
            interval_groups = defaultdict(list)
            mean_interval = statistics.mean(intervals)
            
            for interval in intervals:
                # Group intervals within 10% of each other
                normalized = round(interval / (mean_interval * 0.1)) * (mean_interval * 0.1)
                interval_groups[normalized].append(interval)
                
            # Find the most common interval
            largest_group = max(interval_groups.values(), key=len)
            pattern_strength = len(largest_group) / len(intervals)
            
            return {
                'pattern_detected': pattern_strength > self.significance_threshold,
                'common_interval': round(sum(largest_group) / len(largest_group), 1),
                'pattern_strength': pattern_strength,
                'interval_variations': len(interval_groups)
            }
            
        except Exception as e:
            logger.error(f"Error detecting interval patterns: {str(e)}")
            return {'pattern_detected': False}
            
    def _analyze_amount_patterns(self, amounts: List[float]) -> Dict:
        """Analyze patterns in transaction amounts"""
        try:
            # Group similar amounts
            amount_groups = defaultdict(list)
            mean_amount = statistics.mean(amounts)
            
            for amount in amounts:
                # Group amounts within 1% of each other
                normalized = round(amount / (mean_amount * 0.01)) * (mean_amount * 0.01)
                amount_groups[normalized].append(amount)
                
            # Find the most common amount
            largest_group = max(amount_groups.values(), key=len)
            pattern_strength = len(largest_group) / len(amounts)
            
            return {
                'pattern_detected': pattern_strength > self.significance_threshold,
                'common_amount': round(sum(largest_group) / len(largest_group), 2),
                'pattern_strength': pattern_strength,
                'amount_variations': len(amount_groups),
                'stability_score': self._calculate_amount_stability(amounts)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing amount patterns: {str(e)}")
            return {'pattern_detected': False}
            
    def _analyze_usage_frequency(self, dates: List[datetime]) -> Dict:
        """Analyze the frequency of account usage"""
        try:
            if len(dates) < 2:
                return {'frequency_type': 'irregular'}
                
            date_range = (max(dates) - min(dates)).days
            if date_range == 0:
                return {'frequency_type': 'single_day'}
                
            transactions_per_day = len(dates) / date_range
            
            # Categorize frequency
            if transactions_per_day >= 0.9:
                frequency_type = 'daily'
            elif transactions_per_day >= 0.15:
                frequency_type = 'weekly'
            elif transactions_per_day >= 0.03:
                frequency_type = 'monthly'
            else:
                frequency_type = 'irregular'
                
            return {
                'frequency_type': frequency_type,
                'transactions_per_day': round(transactions_per_day, 3),
                'activity_days': len(set(d.date() for d in dates)),
                'total_days': date_range
            }
            
        except Exception as e:
            logger.error(f"Error analyzing usage frequency: {str(e)}")
            return {'frequency_type': 'error'}
            
    def _calculate_confidence_score(self, basic_stats: Dict,
                                  temporal_patterns: Dict,
                                  amount_patterns: Dict,
                                  usage_frequency: Dict) -> float:
        """Calculate overall confidence score for the pattern analysis"""
        try:
            scores = []
            
            # Score based on amount stability
            if amount_patterns.get('pattern_detected'):
                scores.append(amount_patterns['pattern_strength'])
                
            # Score based on temporal patterns
            if temporal_patterns.get('pattern_detected'):
                scores.append(temporal_patterns.get('regularity_score', 0))
                
            # Score based on frequency
            if usage_frequency.get('frequency_type') != 'irregular':
                scores.append(min(1.0, usage_frequency.get('transactions_per_day', 0) * 5))
                
            # Calculate final confidence score
            if scores:
                return round(sum(scores) / len(scores), 2)
            return 0.0
            
        except Exception as e:
            logger.error(f"Error calculating confidence score: {str(e)}")
            return 0.0
            
    def _calculate_regularity_score(self, intervals: List[int]) -> float:
        """Calculate how regular the transaction intervals are"""
        if not intervals:
            return 0.0
            
        try:
            mean_interval = statistics.mean(intervals)
            if mean_interval == 0:
                return 0.0
                
            # Calculate variation coefficient
            std_dev = statistics.stdev(intervals) if len(intervals) > 1 else 0
            variation_coef = std_dev / mean_interval
            
            # Convert to a score between 0 and 1
            # Lower variation means higher regularity
            return round(max(0.0, min(1.0, 1 - variation_coef)), 2)
            
        except Exception as e:
            logger.error(f"Error calculating regularity score: {str(e)}")
            return 0.0
            
    def _calculate_amount_stability(self, amounts: List[float]) -> float:
        """Calculate the stability of transaction amounts"""
        if not amounts:
            return 0.0
            
        try:
            mean_amount = statistics.mean(amounts)
            if mean_amount == 0:
                return 0.0
                
            # Calculate relative standard deviation
            std_dev = statistics.stdev(amounts) if len(amounts) > 1 else 0
            relative_std = std_dev / mean_amount
            
            # Convert to a stability score between 0 and 1
            return round(max(0.0, min(1.0, 1 - relative_std)), 2)
            
        except Exception as e:
            logger.error(f"Error calculating amount stability: {str(e)}")
            return 0.0
            
    def _analyze_daily_pattern(self, dates: List[datetime]) -> Dict:
        """Analyze patterns in daily transaction timing"""
        try:
            hour_counts = defaultdict(int)
            for date in dates:
                hour_counts[date.hour] += 1
                
            if not hour_counts:
                return {'pattern_detected': False}
                
            most_common_hour = max(hour_counts.items(), key=lambda x: x[1])
            pattern_strength = most_common_hour[1] / len(dates)
            
            return {
                'pattern_detected': pattern_strength > self.significance_threshold,
                'most_common_hour': most_common_hour[0],
                'pattern_strength': pattern_strength
            }
            
        except Exception as e:
            logger.error(f"Error analyzing daily pattern: {str(e)}")
            return {'pattern_detected': False}
            
    def _analyze_weekly_pattern(self, dates: List[datetime]) -> Dict:
        """Analyze patterns in weekly transaction timing"""
        try:
            day_counts = defaultdict(int)
            for date in dates:
                day_counts[date.strftime('%A')] += 1
                
            if not day_counts:
                return {'pattern_detected': False}
                
            most_common_day = max(day_counts.items(), key=lambda x: x[1])
            pattern_strength = most_common_day[1] / len(dates)
            
            return {
                'pattern_detected': pattern_strength > self.significance_threshold,
                'most_common_day': most_common_day[0],
                'pattern_strength': pattern_strength
            }
            
        except Exception as e:
            logger.error(f"Error analyzing weekly pattern: {str(e)}")
            return {'pattern_detected': False}
            
    def _analyze_monthly_pattern(self, dates: List[datetime]) -> Dict:
        """Analyze patterns in monthly transaction timing"""
        try:
            day_counts = defaultdict(int)
            for date in dates:
                day_counts[date.day] += 1
                
            if not day_counts:
                return {'pattern_detected': False}
                
            most_common_day = max(day_counts.items(), key=lambda x: x[1])
            pattern_strength = most_common_day[1] / len(dates)
            
            return {
                'pattern_detected': pattern_strength > self.significance_threshold,
                'most_common_day': most_common_day[0],
                'pattern_strength': pattern_strength
            }
            
        except Exception as e:
            logger.error(f"Error analyzing monthly pattern: {str(e)}")
            return {'pattern_detected': False}
