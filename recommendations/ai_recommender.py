import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy import func
import numpy as np

logger = logging.getLogger(__name__)

class FinancialRecommender:
    """AI-powered financial recommendation system"""
    
    def __init__(self):
        self.recommendation_thresholds = {
            'cashflow_ratio': {'low': 1.5, 'medium': 2.0, 'high': 3.0},
            'expense_growth': {'low': 0.05, 'medium': 0.10, 'high': 0.15},
            'revenue_growth': {'low': 0.10, 'medium': 0.15, 'high': 0.20},
            'profit_margin': {'low': 0.05, 'medium': 0.10, 'high': 0.15}
        }
    
    def generate_recommendations(self, transactions: List[Any], accounts: List[Any]) -> List[Dict]:
        """Generate financial recommendations based on transaction and account data"""
        try:
            # Calculate key financial metrics
            metrics = self._calculate_financial_metrics(transactions, accounts)
            
            # Analyze patterns and trends
            patterns = self._analyze_patterns(transactions)
            
            # Generate recommendations based on metrics and patterns
            recommendations = []
            
            # Cash flow recommendations
            if metrics['cashflow_ratio'] < self.recommendation_thresholds['cashflow_ratio']['medium']:
                recommendations.append({
                    'category': 'cashflow',
                    'priority': 'high' if metrics['cashflow_ratio'] < self.recommendation_thresholds['cashflow_ratio']['low'] else 'medium',
                    'recommendation': 'Consider implementing stricter payment collection policies and negotiating extended payment terms with suppliers.',
                    'impact_score': (self.recommendation_thresholds['cashflow_ratio']['medium'] - metrics['cashflow_ratio']) * 10
                })
            
            # Expense management recommendations
            if metrics['expense_growth'] > self.recommendation_thresholds['expense_growth']['medium']:
                recommendations.append({
                    'category': 'cost_reduction',
                    'priority': 'high' if metrics['expense_growth'] > self.recommendation_thresholds['expense_growth']['high'] else 'medium',
                    'recommendation': 'Review and optimize operational expenses, focusing on areas with significant cost increases.',
                    'impact_score': metrics['expense_growth'] * 100
                })
            
            # Revenue growth recommendations
            if metrics['revenue_growth'] < self.recommendation_thresholds['revenue_growth']['medium']:
                recommendations.append({
                    'category': 'revenue',
                    'priority': 'high' if metrics['revenue_growth'] < self.recommendation_thresholds['revenue_growth']['low'] else 'medium',
                    'recommendation': 'Consider diversifying revenue streams and implementing targeted marketing strategies.',
                    'impact_score': (self.recommendation_thresholds['revenue_growth']['medium'] - metrics['revenue_growth']) * 100
                })
            
            # Add pattern-based recommendations
            for pattern in patterns:
                recommendations.append(self._generate_pattern_recommendation(pattern))
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            return []
    
    def _calculate_financial_metrics(self, transactions: List[Any], accounts: List[Any]) -> Dict:
        """Calculate key financial metrics from transaction data"""
        try:
            current_month = datetime.now().replace(day=1)
            last_month = current_month - timedelta(days=1)
            last_month = last_month.replace(day=1)
            
            # Calculate current month metrics
            current_income = sum(t.amount for t in transactions 
                               if t.date >= current_month and t.amount > 0)
            current_expenses = abs(sum(t.amount for t in transactions 
                                     if t.date >= current_month and t.amount < 0))
            
            # Calculate last month metrics
            last_income = sum(t.amount for t in transactions 
                            if last_month <= t.date < current_month and t.amount > 0)
            last_expenses = abs(sum(t.amount for t in transactions 
                                  if last_month <= t.date < current_month and t.amount < 0))
            
            # Calculate growth rates
            revenue_growth = ((current_income - last_income) / last_income) if last_income else 0
            expense_growth = ((current_expenses - last_expenses) / last_expenses) if last_expenses else 0
            
            # Calculate cash flow ratio
            cashflow_ratio = current_income / current_expenses if current_expenses else float('inf')
            
            # Calculate profit margin
            profit_margin = (current_income - current_expenses) / current_income if current_income else 0
            
            return {
                'cashflow_ratio': cashflow_ratio,
                'revenue_growth': revenue_growth,
                'expense_growth': expense_growth,
                'profit_margin': profit_margin
            }
            
        except Exception as e:
            logger.error(f"Error calculating financial metrics: {str(e)}")
            return {}
    
    def _analyze_patterns(self, transactions: List[Any]) -> List[Dict]:
        """Analyze transaction patterns for insights"""
        try:
            patterns = []
            
            # Group transactions by category
            category_totals = {}
            for transaction in transactions:
                category = transaction.category or 'Uncategorized'
                if category not in category_totals:
                    category_totals[category] = {'count': 0, 'amount': 0}
                category_totals[category]['count'] += 1
                category_totals[category]['amount'] += transaction.amount
            
            # Identify significant patterns
            for category, data in category_totals.items():
                if data['count'] >= 3:  # Pattern threshold
                    patterns.append({
                        'type': 'frequency',
                        'category': category,
                        'count': data['count'],
                        'amount': data['amount']
                    })
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error analyzing patterns: {str(e)}")
            return []
    
    def _generate_pattern_recommendation(self, pattern: Dict) -> Dict:
        """Generate recommendations based on identified patterns"""
        try:
            if pattern['type'] == 'frequency' and pattern['amount'] < 0:
                return {
                    'category': 'pattern_insight',
                    'priority': 'medium',
                    'recommendation': f'Consider reviewing frequent expenses in {pattern["category"]} category for potential cost optimization.',
                    'impact_score': abs(pattern['amount']) / pattern['count']
                }
            return None
            
        except Exception as e:
            logger.error(f"Error generating pattern recommendation: {str(e)}")
            return None
