import os
import logging
import openai
from datetime import datetime
from typing import List, Dict, Optional
from tenacity import retry, stop_after_attempt, wait_exponential
from nlp_utils import get_openai_client, clean_text
from models import db, ErrorLog

# Configure logging
logger = logging.getLogger(__name__)
handler = logging.FileHandler('ai_service.log')
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)
logger.setLevel(logging.ERROR)

class ServiceStatus:
    def __init__(self):
        self.consecutive_failures = 0
        self.error_count = 0
        self.last_success = None
        self.last_error = None

class FinancialInsightsGenerator:
    def __init__(self):
        self.service_status = ServiceStatus()
        self.client = None
        self.client_error = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize OpenAI client with proper error handling"""
        try:
            logger.debug("Starting OpenAI client initialization in FinancialInsightsGenerator")
            self.client = get_openai_client()
            
            if self.client is None:
                logger.error("get_openai_client() returned None")
                raise ValueError("Failed to initialize OpenAI client")
                
            self.client_error = None
            logger.info("OpenAI client initialized successfully in FinancialInsightsGenerator")
            
        except Exception as e:
            self.client_error = str(e)
            logger.error(f"Error initializing OpenAI client: {str(e)}", exc_info=True)
            logger.debug(f"Client initialization error details - Type: {type(e).__name__}, Args: {e.args}")
            self._log_error("OpenAI Client Initialization", str(e))

    def _log_error(self, error_type, message):
        """Log error to database and update service status"""
        try:
            error_log = ErrorLog(
                timestamp=datetime.utcnow(),
                error_type=error_type,
                error_message=message
            )
            db.session.add(error_log)
            db.session.commit()

            self.service_status.error_count += 1
            self.service_status.consecutive_failures += 1
            self.service_status.last_error = datetime.utcnow()
        except Exception as e:
            logger.error(f"Failed to log error: {str(e)}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate_insight(self, transaction_data):
        """Generate financial insights with retries and error handling"""
        if self.client is None:
            self._initialize_client()
            if self.client is None:
                raise ValueError("OpenAI client unavailable")

        try:
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a financial analyst assistant."},
                    {"role": "user", "content": f"Analyze this transaction: {clean_text(str(transaction_data))}"}
                ],
                max_tokens=150,
                temperature=0.7
            )

            self.service_status.consecutive_failures = 0
            self.service_status.last_success = datetime.utcnow()
            return response.choices[0].message.content

        except Exception as e:
            error_msg = f"Failed to generate insight: {str(e)}"
            self._log_error("AI Insight Generation", error_msg)
            raise

    def get_service_health(self):
        """Return current service health status"""
        return {
            'status': 'healthy' if self.client_error is None else 'degraded',
            'consecutive_failures': self.service_status.consecutive_failures,
            'error_count': self.service_status.error_count,
            'last_success': self.service_status.last_success,
            'last_error': self.service_status.last_error,
            'client_status': 'initialized' if self.client else 'failed'
        }

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

    def _generate_fallback_insights(self, transactions: List[Dict], error: Optional[str] = None) -> Dict:
        """Generate basic insights without AI when service is unavailable."""
        try:
            if not transactions or not isinstance(transactions, list):
                return {
                    'success': True,
                    'insights': "No transactions to analyze",
                    'generated_at': datetime.now().isoformat(),
                    'analysis_type': 'basic',
                    'error': error,
                    'service_status': {
                        'error_count': self.service_status.error_count,
                        'last_error': self.service_status.last_error
                    },
                    'category_suggestion': {
                        'category': None,
                        'confidence': 0,
                        'explanation': "No transaction to analyze"
                    }
                }

            # Process valid transaction data
            if isinstance(transactions[0], dict):
                latest = transactions[0]
                amount = latest.get('amount', 0)

                total_income = sum(t.get('amount', 0) for t in transactions if t.get('amount', 0) > 0)
                total_expenses = sum(abs(t.get('amount', 0)) for t in transactions if t.get('amount', 0) < 0)
                net_change = total_income - total_expenses

                category_guess = "expense" if amount < 0 else "income"

                insights = (
                    f"Basic Financial Analysis:\n"
                    f"- Total Income: ${total_income:,.2f}\n"
                    f"- Total Expenses: ${total_expenses:,.2f}\n"
                    f"- Net Change: ${net_change:,.2f}\n\n"
                    f"Transaction appears to be an {category_guess}.\n"
                    f"This is a basic analysis generated without AI assistance."
                )

                if error:
                    insights += f"\n\nNote: {error}"

                return {
                    'success': True,
                    'insights': insights,
                    'generated_at': datetime.now().isoformat(),
                    'analysis_type': 'basic',
                    'error': error,
                    'service_status': {
                        'error_count': self.service_status.error_count,
                        'last_error': self.service_status.last_error
                    },
                    'category_suggestion': {
                        'category': category_guess,
                        'confidence': 0.5,
                        'explanation': f"Basic categorization based on amount being {'negative' if amount < 0 else 'positive'}"
                    }
                }
            else:
                logger.error("Invalid transaction data format")
                return {
                    'success': False,
                    'error': "Invalid transaction data format",
                    'analysis_type': 'error',
                    'service_status': {
                        'error_count': self.service_status.error_count,
                        'last_error': self.service_status.last_error
                    }
                }

        except Exception as e:
            logger.error(f"Critical error in fallback analysis: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'generated_at': datetime.now().isoformat(),
                'analysis_type': 'error',
                'service_status': {
                    'error_count': self.service_status.error_count,
                    'last_error': self.service_status.last_error
                },
                'category_suggestion': {
                    'category': None,
                    'confidence': 0,
                    'explanation': f"Error in fallback analysis: {str(e)}"
                }
            }

    async def generate_transaction_insights(self, transaction_data: List[Dict]) -> Dict:
        """Generate AI-powered insights for transactions with enhanced error handling."""
        try:
            if not isinstance(transaction_data, list) or not transaction_data:
                logger.error("Invalid or empty transaction data provided")
                return self._generate_fallback_insights([], error="No valid transaction data provided")

            # For single transaction analysis, use the first transaction
            transaction = transaction_data[0]

            if self.client is None:
                logger.warning("AI service client unavailable, using fallback analysis")
                return self._generate_fallback_insights([transaction], error="AI service temporarily unavailable")


            try:
                insights = await self.generate_insight(transaction)
                self.service_status.last_success = datetime.utcnow()
                self.service_status.consecutive_failures = 0

                return {
                    'success': True,
                    'insights': insights,
                    'generated_at': datetime.now().isoformat(),
                    'analysis_type': 'ai_powered',
                    'service_status': {
                        'error_count': self.service_status.error_count,
                        'last_success': self.service_status.last_success.isoformat() if self.service_status.last_success else None
                    },
                    'category_suggestion': {
                        'category': None,
                        'confidence': 0,
                        'explanation': None
                    }
                }
            except Exception as e:
                logger.error(f"Error generating insights: {str(e)}")
                self._log_error("AI Insight Generation", str(e))
                return self._generate_fallback_insights([transaction], error=f"AI service error: {str(e)}")
        except Exception as e:
            logger.error(f"Critical error in insight generation: {str(e)}")
            self._log_error("Critical Error", str(e))
            return self._generate_fallback_insights(
                [transaction_data[0]] if transaction_data else [],
                error=f"Critical error: {str(e)}"
            )


    async def generate_insights(self, transactions: List[Dict]) -> Dict:
        """Generate insights from transaction data using AI."""
        try:
            if self.client is None:
                return self._generate_fallback_insights(transactions)

            # Prepare transaction data for analysis
            transaction_summary = self._prepare_transaction_summary(transactions)

            # Get AI categorization for the latest transaction
            latest_transaction = transactions[0] if transactions else None
            category, confidence, explanation = None, 0, "No transaction to analyze"
            if latest_transaction:
                try:
                    category, confidence, explanation = categorize_transaction(latest_transaction['description'])
                except (openai.APIError, openai.RateLimitError) as e:
                    logger.error(f"AI API Error in categorization: {str(e)}")
                    self._log_error("AI Categorization", str(e))
                    return self._generate_fallback_insights(transactions, error=f"AI service error during categorization: {str(e)}")
                except Exception as e:
                    logger.error(f"Unexpected error in categorization: {str(e)}")
                    self._log_error("AI Categorization", str(e))
                    category, confidence, explanation = None, 0, "Categorization unavailable"

            # Generate combined insights using OpenAI with environment-specific handling
            try:
                insights = await self.generate_insight(transaction_summary)
                self.service_status.last_success = datetime.utcnow()
                self.service_status.consecutive_failures = 0

                return {
                    'success': True,
                    'insights': insights,
                    'generated_at': datetime.now().isoformat(),
                    'analysis_type': 'ai_powered',
                    'service_status': {
                        'error_count': self.service_status.error_count,
                        'last_success': self.service_status.last_success.isoformat() if self.service_status.last_success else None
                    },
                    'category_suggestion': {
                        'category': category,
                        'confidence': confidence,
                        'explanation': explanation
                    }
                }

            except (openai.APIError, openai.RateLimitError) as e:
                logger.error(f"OpenAI API Error: {str(e)}")
                self._log_error("AI Insight Generation", str(e))
                return self._generate_fallback_insights(transactions, error=f"AI service error: {str(e)}")
            except Exception as e:
                logger.error(f"Unexpected error generating insights: {str(e)}")
                self._log_error("AI Insight Generation", str(e))
                insights = "AI insights currently unavailable. Using basic analysis."

                return {
                    'success': True,
                    'insights': insights,
                    'generated_at': datetime.now().isoformat(),
                    'analysis_type': 'ai_powered',
                    'service_status': {
                        'error_count': self.service_status.error_count,
                        'last_success': self.service_status.last_success.isoformat() if self.service_status.last_success else None
                    },
                    'category_suggestion': {
                        'category': category,
                        'confidence': confidence,
                        'explanation': explanation
                    }
                }

        except Exception as e:
            logger.error(f"Critical error generating insights: {str(e)}")
            self._log_error("Critical Error", str(e))
            return self._generate_fallback_insights(transactions, error=f"Critical error: {str(e)}")