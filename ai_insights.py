import os
import logging
from typing import Dict, List
import openai
from datetime import datetime

logger = logging.getLogger(__name__)

class FinancialInsightsGenerator:
    def __init__(self):
        self.api_key = os.environ.get('OPENAI_API_KEY')
        if self.api_key:
            openai.api_key = self.api_key

    def generate_transaction_insights(self, transactions: List[Dict], period: str = "current") -> Dict:
        """Generate insights from transaction data using AI."""
        try:
            if not self.api_key:
                return self._generate_fallback_insights(transactions)

            # Prepare transaction data for analysis
            transaction_summary = self._prepare_transaction_summary(transactions)
            
            # Generate AI insights using OpenAI
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a financial analyst providing insights on transaction data."},
                    {"role": "user", "content": f"Analyze these financial transactions and provide key insights: {transaction_summary}"}
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            insights = response.choices[0].message.content
            
            return {
                'success': True,
                'insights': insights,
                'generated_at': datetime.now().isoformat(),
                'analysis_type': 'ai_powered'
            }
            
        except Exception as e:
            logger.error(f"Error generating AI insights: {str(e)}")
            return self._generate_fallback_insights(transactions)

    def _prepare_transaction_summary(self, transactions: List[Dict]) -> str:
        """Prepare transaction data for AI analysis."""
        total_income = sum(t['amount'] for t in transactions if t['amount'] > 0)
        total_expenses = sum(abs(t['amount']) for t in transactions if t['amount'] < 0)
        transaction_count = len(transactions)
        
        # Categorize transactions
        categories = {}
        for t in transactions:
            category = t.get('category', 'Uncategorized')
            if category not in categories:
                categories[category] = {'count': 0, 'total': 0}
            categories[category]['count'] += 1
            categories[category]['total'] += abs(t['amount'])

        summary = (
            f"Financial Summary:\n"
            f"Total Income: ${total_income:,.2f}\n"
            f"Total Expenses: ${total_expenses:,.2f}\n"
            f"Transaction Count: {transaction_count}\n\n"
            f"Category Breakdown:\n"
        )
        
        for category, data in categories.items():
            summary += f"- {category}: ${data['total']:,.2f} ({data['count']} transactions)\n"
            
        return summary

    def _generate_fallback_insights(self, transactions: List[Dict]) -> Dict:
        """Generate basic insights without AI when API is unavailable."""
        try:
            total_income = sum(t['amount'] for t in transactions if t['amount'] > 0)
            total_expenses = sum(abs(t['amount']) for t in transactions if t['amount'] < 0)
            net_change = total_income - total_expenses
            
            insights = (
                f"Basic Financial Summary:\n"
                f"- Total Income: ${total_income:,.2f}\n"
                f"- Total Expenses: ${total_expenses:,.2f}\n"
                f"- Net Change: ${net_change:,.2f}\n\n"
                f"This is a basic analysis generated without AI assistance."
            )
            
            return {
                'success': True,
                'insights': insights,
                'generated_at': datetime.now().isoformat(),
                'analysis_type': 'basic'
            }
            
        except Exception as e:
            logger.error(f"Error generating fallback insights: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'generated_at': datetime.now().isoformat(),
                'analysis_type': 'error'
            }
