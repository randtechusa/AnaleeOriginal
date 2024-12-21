import os
import logging
from typing import Dict, List
from datetime import datetime
from openai import OpenAI
from nlp_utils import get_openai_client, categorize_transaction

logger = logging.getLogger(__name__)

class FinancialInsightsGenerator:
    def __init__(self):
        self.api_key = os.environ.get('OPENAI_API_KEY')
        self.client = get_openai_client() if self.api_key else None
        self.env = os.environ.get('FLASK_ENV', 'development')

    def generate_insights(self, transactions: List[Dict]) -> Dict:
        """Generate insights from transaction data using AI."""
        try:
            if not self.client:
                return self._generate_fallback_insights(transactions)

            # Prepare transaction data for analysis
            transaction_summary = self._prepare_transaction_summary(transactions)

            # Get AI categorization for the latest transaction
            latest_transaction = transactions[0] if transactions else None
            if latest_transaction:
                try:
                    category, confidence, explanation = categorize_transaction(latest_transaction['description'])
                except Exception as e:
                    logger.error(f"Error in categorization: {str(e)}")
                    category, confidence, explanation = None, 0, "Categorization unavailable"
            else:
                category, confidence, explanation = None, 0, "No transaction to analyze"

            # Generate combined insights using OpenAI with environment-specific handling
            try:
                if self.env == 'production':
                    # Production: More conservative token usage and caching
                    max_tokens = 300
                    temperature = 0.5
                else:
                    # Development: More experimental
                    max_tokens = 500
                    temperature = 0.7

                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a financial analyst providing insights on transaction data."},
                        {"role": "user", "content": f"Analyze these financial transactions and provide key insights: {transaction_summary}"}
                    ],
                    max_tokens=max_tokens,
                    temperature=temperature
                )

                insights = response.choices[0].message.content

            except Exception as e:
                logger.error(f"Error generating OpenAI insights: {str(e)}")
                insights = "AI insights currently unavailable. Using basic analysis."

            return {
                'success': True,
                'insights': insights,
                'generated_at': datetime.now().isoformat(),
                'analysis_type': 'ai_powered',
                'category_suggestion': {
                    'category': category,
                    'confidence': confidence,
                    'explanation': explanation
                }
            }

        except Exception as e:
            logger.error(f"Error generating AI insights: {str(e)}")
            return self._generate_fallback_insights(transactions)

    def _prepare_transaction_summary(self, transactions: List[Dict]) -> str:
        """Prepare transaction data for AI analysis."""
        if not transactions:
            return "No transactions to analyze"

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

        # Add latest transaction details for better context
        if transactions:
            latest = transactions[0]
            summary += f"\nLatest Transaction:\n"
            summary += f"Description: {latest.get('description', 'N/A')}\n"
            summary += f"Amount: ${abs(latest.get('amount', 0)):,.2f} "
            summary += "credit" if latest.get('amount', 0) < 0 else "debit"

        return summary

    def _generate_fallback_insights(self, transactions: List[Dict]) -> Dict:
        """Generate basic insights without AI when API is unavailable."""
        try:
            if not transactions:
                return {
                    'success': True,
                    'insights': "No transactions to analyze",
                    'generated_at': datetime.now().isoformat(),
                    'analysis_type': 'basic',
                    'category_suggestion': {
                        'category': None,
                        'confidence': 0,
                        'explanation': "No transaction to analyze"
                    }
                }

            total_income = sum(t['amount'] for t in transactions if t['amount'] > 0)
            total_expenses = sum(abs(t['amount']) for t in transactions if t['amount'] < 0)
            net_change = total_income - total_expenses

            latest = transactions[0]
            category_guess = "expense" if latest.get('amount', 0) < 0 else "income"

            insights = (
                f"Basic Financial Summary:\n"
                f"- Total Income: ${total_income:,.2f}\n"
                f"- Total Expenses: ${total_expenses:,.2f}\n"
                f"- Net Change: ${net_change:,.2f}\n\n"
                f"Transaction appears to be an {category_guess}.\n"
                f"This is a basic analysis generated without AI assistance."
            )

            return {
                'success': True,
                'insights': insights,
                'generated_at': datetime.now().isoformat(),
                'analysis_type': 'basic',
                'category_suggestion': {
                    'category': category_guess,
                    'confidence': 0.5,
                    'explanation': f"Basic categorization based on amount being {'negative' if latest.get('amount', 0) < 0 else 'positive'}"
                }
            }

        except Exception as e:
            logger.error(f"Error generating fallback insights: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'generated_at': datetime.now().isoformat(),
                'analysis_type': 'error',
                'category_suggestion': {
                    'category': None,
                    'confidence': 0,
                    'explanation': f"Error in categorization: {str(e)}"
                }
            }