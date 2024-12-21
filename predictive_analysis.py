"""
AI-Powered Financial Trend Analysis Module
Provides predictive analytics while maintaining separation from core functionalities
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import pandas as pd
import numpy as np
from sqlalchemy import func

from models import db, Transaction, Account
from ai_insights import FinancialInsightsGenerator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FinancialTrendAnalyzer:
    """
    Handles predictive financial trend analysis using AI/ML techniques
    while maintaining separation from core functionalities
    """
    def __init__(self):
        self.insights_generator = FinancialInsightsGenerator()
        
    def analyze_trends(self, user_id: int, months_back: int = 12) -> Dict:
        """
        Analyze financial trends and generate predictions
        
        Args:
            user_id: User ID to analyze
            months_back: Number of months of historical data to analyze
            
        Returns:
            Dictionary containing trend analysis and predictions
        """
        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=months_back * 30)
            
            # Get transaction data
            transactions = Transaction.query.filter(
                Transaction.user_id == user_id,
                Transaction.date.between(start_date, end_date)
            ).order_by(Transaction.date).all()
            
            if not transactions:
                return {
                    'status': 'error',
                    'message': 'Insufficient historical data for analysis'
                }
                
            # Convert to pandas DataFrame for analysis
            df = pd.DataFrame([{
                'date': t.date,
                'amount': float(t.amount),
                'category': t.account.category if t.account else 'Uncategorized'
            } for t in transactions])
            
            # Calculate key metrics
            metrics = self._calculate_metrics(df)
            
            # Generate predictions
            predictions = self._generate_predictions(df)
            
            # Get AI insights
            ai_insights = self._get_ai_insights(df)
            
            return {
                'status': 'success',
                'metrics': metrics,
                'predictions': predictions,
                'insights': ai_insights
            }
            
        except Exception as e:
            logger.error(f"Error in trend analysis: {str(e)}")
            return {
                'status': 'error',
                'message': f'Error analyzing trends: {str(e)}'
            }
            
    def _calculate_metrics(self, df: pd.DataFrame) -> Dict:
        """Calculate key financial metrics"""
        try:
            metrics = {
                'total_transactions': len(df),
                'average_transaction': df['amount'].mean(),
                'monthly_totals': df.groupby(df['date'].dt.strftime('%Y-%m'))['amount'].sum().to_dict(),
                'category_totals': df.groupby('category')['amount'].sum().to_dict()
            }
            
            # Calculate growth rates
            monthly_series = df.groupby(df['date'].dt.strftime('%Y-%m'))['amount'].sum()
            if len(monthly_series) > 1:
                metrics['monthly_growth_rate'] = (
                    (monthly_series.iloc[-1] - monthly_series.iloc[0]) / 
                    abs(monthly_series.iloc[0]) * 100
                )
            else:
                metrics['monthly_growth_rate'] = 0
                
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating metrics: {str(e)}")
            return {}
            
    def _generate_predictions(self, df: pd.DataFrame) -> Dict:
        """Generate financial predictions using simple statistical methods"""
        try:
            # Group by month
            monthly_totals = df.groupby(df['date'].dt.strftime('%Y-%m'))['amount'].sum()
            
            if len(monthly_totals) < 2:
                return {
                    'next_month_prediction': None,
                    'confidence': 0,
                    'trend': 'insufficient_data'
                }
                
            # Calculate simple moving average
            sma = monthly_totals.rolling(window=3).mean()
            
            # Calculate basic trend
            trend = 'upward' if monthly_totals.iloc[-1] > monthly_totals.iloc[-2] else 'downward'
            
            # Simple prediction for next month
            next_month = monthly_totals.iloc[-1] * (1 + monthly_totals.pct_change().mean())
            
            return {
                'next_month_prediction': float(next_month),
                'confidence': min(max(float(monthly_totals.pct_change().std() * 100), 0), 100),
                'trend': trend
            }
            
        except Exception as e:
            logger.error(f"Error generating predictions: {str(e)}")
            return {}
            
    def _get_ai_insights(self, df: pd.DataFrame) -> Dict:
        """Get AI-powered insights about the financial trends"""
        try:
            # Convert data for AI analysis
            data_for_ai = [{
                'date': row['date'].isoformat(),
                'amount': row['amount'],
                'category': row['category']
            } for _, row in df.iterrows()]
            
            # Generate insights using existing AI service
            insights = self.insights_generator.generate_transaction_insights(data_for_ai)
            
            return {
                'trends': insights.get('trends', []),
                'recommendations': insights.get('recommendations', []),
                'risk_factors': insights.get('risk_factors', [])
            }
            
        except Exception as e:
            logger.error(f"Error getting AI insights: {str(e)}")
            return {}
