"""
AI-powered accounting assistant for processing financial transactions
Enhanced with proper type checking, validation, and comprehensive features
"""
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from decimal import Decimal, InvalidOperation
from ai_insights import FinancialInsightsGenerator
from nlp_utils import categorize_transaction

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PredictiveFeatures:
    """Enhanced predictive features with proper error handling"""
    def find_similar_transactions(self, description: str = "", explanation: str = "") -> Dict[str, Any]:
        """Find similar transactions with enhanced pattern matching"""
        try:
            #Simulate finding similar transactions. Replace with actual implementation
            similar_transactions = [
                {
                    'description': 'Rent Payment',
                    'explanation': 'Monthly rent expense',
                    'confidence': 0.9,
                    'semantic_similarity': 0.8,
                    'text_similarity': 0.9
                },
                {
                    'description': 'Office Supplies',
                    'explanation': 'Purchase of office supplies',
                    'confidence': 0.7,
                    'semantic_similarity': 0.6,
                    'text_similarity': 0.8
                },
                {
                    'description': 'Payroll',
                    'explanation': 'Employee salaries',
                    'confidence': 0.85,
                    'semantic_similarity': 0.75,
                    'text_similarity': 0.95
                }
            ]
            return {'success': True, 'similar_transactions': similar_transactions}
        except Exception as e:
            logger.error(f"Error finding similar transactions: {str(e)}")
            return {'success': False, 'error': str(e)}

class ICountant:
    """
    AI-powered accounting assistant for guided double-entry transaction processing
    with real-time insights, pattern recognition, and advanced suggestion features
    """
    def __init__(self, available_accounts: List[Dict[str, Any]]):
        """Initialize ICountant with available accounts"""
        self.available_accounts = available_accounts
        self.current_transaction: Optional[Dict[str, Any]] = None
        self.processed_transactions: List[Dict[str, Any]] = []
        self.insights_generator = FinancialInsightsGenerator()

    async def get_transaction_insights(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Generate AI-powered insights with enhanced explanation recognition"""
        try:
            if not transaction:
                logger.error("Empty transaction provided")
                return {}

            # Fallback to pattern matching if AI services fail
            try:
                insights = await self._get_ai_insights(transaction)
            except Exception as e:
                logger.warning(f"AI insights failed, falling back to pattern matching: {str(e)}")
                insights = self._get_pattern_based_insights(transaction)

            # Validate transaction amount
            amount = self._validate_and_convert_amount(transaction.get('amount'))
            if amount is None:
                logger.error("Invalid transaction amount for insights generation")
                return {}

            # Get similar transactions and explanations
            predictor = PredictiveFeatures()
            similar_result = predictor.find_similar_transactions(
                description=transaction.get('description', ''),
                explanation=transaction.get('explanation', '')
            )

            # Get account suggestions
            suggested_accounts = self._suggest_accounts(transaction)

            # Generate base insights
            transaction_insights = await self.insights_generator.generate_transaction_insights([transaction])

            # Generate explanation
            suggested_explanation = self._generate_explanation(transaction)

            # Find similar explanations
            similar_explanations = self._find_similar_explanations(transaction)

            return {
                'similar_transactions': similar_result.get('similar_transactions', []),
                'recognized_explanations': [
                    {
                        'explanation': t['explanation'],
                        'confidence': (t['semantic_similarity'] + t['text_similarity']) / 2,
                        'source_transaction': t['description']
                    }
                    for t in similar_result.get('similar_transactions', [])
                ],
                'ai_insights': transaction_insights[0].get('insights', '') if transaction_insights else '',
                'suggested_accounts': suggested_accounts,
                'suggested_explanation': suggested_explanation,
                'similar_explanations': similar_explanations,
                'transaction_type': 'credit' if amount < 0 else 'debit',
                'amount_formatted': self.format_amount(amount),
                'confidence_score': self._calculate_confidence_score(transaction)
            }

        except Exception as e:
            logger.error(f"Error generating transaction insights: {str(e)}")
            return {}

    def _description_similarity(self, desc1: str, desc2: str) -> bool:
        """Check if descriptions are similar using pattern matching"""
        from difflib import SequenceMatcher
        return SequenceMatcher(None, desc1.lower(), desc2.lower()).ratio() > 0.6

    def _generate_explanation(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Generate AI-powered explanation with enhanced recognition"""
        try:
            description = transaction.get('description', '')
            amount = self._validate_and_convert_amount(transaction.get('amount'))

            # Try pattern matching first
            predictor = PredictiveFeatures()
            similar_result = predictor.find_similar_transactions(description)

            if similar_result.get('success') and similar_result.get('similar_transactions'):
                best_match = max(
                    similar_result['similar_transactions'],
                    key=lambda x: x.get('confidence', 0)
                )

                if best_match.get('confidence', 0) > 0.8:
                    return {
                        'explanation': best_match.get('explanation', ''),
                        'confidence': best_match.get('confidence', 0),
                        'source': 'pattern_match'
                    }

            # Fallback to AI-powered categorization
            category, confidence, base_explanation = categorize_transaction(description)

            return {
                'explanation': f"{base_explanation} - {'Revenue' if amount > 0 else 'Expense'} from {description}",
                'confidence': confidence,
                'source': 'ai_categorization'
            }

        except Exception as e:
            logger.error(f"Error generating explanation: {str(e)}")
            return {
                'explanation': "Transaction recorded - details in description",
                'confidence': 0.5,
                'source': 'fallback'
            }

    def _find_similar_explanations(self, transaction: Dict[str, Any]) -> List[str]:
        """Find similar explanations from historical transactions"""
        try:
            current_desc = transaction.get('description', '').lower()
            similar_explanations = []

            for past_transaction in self.processed_transactions:
                if ('explanation' in past_transaction and 
                    self._description_similarity(current_desc, past_transaction['description'].lower())):
                    similar_explanations.append(past_transaction['explanation'])

            return list(set(similar_explanations))[:3]
        except Exception as e:
            logger.error(f"Error finding similar explanations: {str(e)}")
            return []

    def _validate_and_convert_amount(self, amount) -> Optional[Decimal]:
        """Validate and convert amount to Decimal"""
        try:
            if amount is None or isinstance(amount, str) and not amount.strip():
                return None
            decimal_amount = Decimal(str(amount))
            if decimal_amount == 0:
                raise ValueError("Amount cannot be zero")
            return decimal_amount
        except (InvalidOperation, TypeError, ValueError) as e:
            logger.error(f"Amount validation error: {str(e)}")
            return None

    def _suggest_accounts(self, transaction: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Suggest relevant accounts based on transaction details"""
        try:
            amount = self._validate_and_convert_amount(transaction.get('amount'))
            if amount is None:
                logger.error("Invalid amount for account suggestion")
                return []

            is_income = amount > 0
            suggested = []

            for account in self.available_accounts:
                category = account['category'].lower()
                if is_income and category in ['revenue', 'income', 'sales']:
                    suggested.append({
                        'account': account,
                        'confidence': 0.8,
                        'reason': 'Common income account'
                    })
                elif not is_income and category in ['expense', 'expenses', 'cost']:
                    suggested.append({
                        'account': account,
                        'confidence': 0.8,
                        'reason': 'Common expense account'
                    })

            return sorted(suggested, key=lambda x: x['confidence'], reverse=True)[:3]
        except Exception as e:
            logger.error(f"Error suggesting accounts: {str(e)}")
            return []

    def validate_amount(self, amount) -> Tuple[bool, Optional[Decimal], str]:
        """Validate transaction amount"""
        try:
            decimal_amount = self._validate_and_convert_amount(amount)
            if decimal_amount is None:
                return False, None, "Invalid amount or amount cannot be zero"
            return True, decimal_amount, "Amount validated successfully"
        except Exception as e:
            logger.error(f"Amount validation error: {str(e)}")
            return False, None, f"Invalid amount format: {str(e)}"

    def format_amount(self, amount: Decimal) -> str:
        """Format amount for display with proper sign"""
        return f"${abs(amount):,.2f} {'credit' if amount < 0 else 'debit'}"

    def get_account_options(self) -> str:
        """Format available accounts for display"""
        return "\n".join([
            f"{i+1}. {acc['name']} ({acc['category']})"
            for i, acc in enumerate(self.available_accounts)
        ])

    def _calculate_confidence_score(self, transaction: Dict[str, Any]) -> float:
        """Calculate a confidence score for the transaction processing"""
        return 0.9  # Default confidence score for now

    async def process_transaction(self, transaction: Dict[str, Any]) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Process a single transaction and guide the user through account selection
        Returns: (message_to_user, transaction_info)
        """
        try:
            # Initial validation
            if not transaction:
                return "No transaction data provided", None

            # Validate transaction data
            if not isinstance(transaction, dict):
                return "Invalid transaction data format", None

            # Validate required fields
            if 'amount' not in transaction:
                return "Transaction amount is required", None
            if 'description' not in transaction:
                return "Transaction description is required", None

            # Validate and convert amount
            amount = self._validate_and_convert_amount(transaction.get('amount'))
            if amount is None:
                return "Invalid transaction amount", None

            self.current_transaction = transaction

            # Generate insights for the transaction
            transaction_insights = await self.get_transaction_insights(transaction)

            # Bank account is the default first entry
            bank_entry = {
                'account': 'Bank',
                'amount': amount,
                'description': transaction.get('description', 'No description provided'),
                'date': transaction.get('date', datetime.now())
            }

            # Build guidance message with insights
            message = (
                f"Transaction Analysis:\n"
                f"Description: {transaction.get('description', 'No description')}\n"
                f"Amount: {self.format_amount(amount)}\n"
                f"Type: {'Income/Revenue' if amount > 0 else 'Expense/Payment'} Transaction\n\n"
                f"AI Insights:\n{transaction_insights.get('ai_insights', 'No insights available')}\n\n"
                f"Suggested Accounts:\n"
            )

            for suggestion in transaction_insights.get('suggested_accounts', []):
                message += f"- {suggestion['account']['name']} ({suggestion['reason']})\n"

            message += f"\nAvailable Accounts:\n{self.get_account_options()}\n"
            message += f"Please select the account number for the {'credit' if amount > 0 else 'debit'} entry."

            return message, {
                'bank_entry': bank_entry,
                'entry_type_needed': 'credit' if amount > 0 else 'debit',
                'original_transaction': transaction,
                'insights': transaction_insights
            }

        except Exception as e:
            logger.error(f"Error processing transaction: {str(e)}")
            return f"Error processing transaction: {str(e)}", None

    def complete_transaction(self, selected_account_index: int) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Complete the transaction with the selected account"""
        if not self.current_transaction:
            return False, "No transaction in progress", None

        try:
            if not (0 <= selected_account_index < len(self.available_accounts)):
                return False, "Invalid account selection", None

            selected_account = self.available_accounts[selected_account_index]
            amount = self._validate_and_convert_amount(self.current_transaction.get('amount'))

            if amount is None:
                return False, "Invalid transaction amount", None

            # Create the double entry
            transaction = {
                'date': self.current_transaction.get('date', datetime.now()),
                'description': self.current_transaction.get('description', 'No description'),
                'entries': [
                    {
                        'account': 'Bank',
                        'debit': amount if amount > 0 else Decimal('0'),
                        'credit': abs(amount) if amount < 0 else Decimal('0')
                    },
                    {
                        'account': selected_account['name'],
                        'debit': abs(amount) if amount < 0 else Decimal('0'),
                        'credit': amount if amount > 0 else Decimal('0')
                    }
                ],
                'metadata': {
                    'processed_by': 'iCountant',
                    'processed_at': datetime.now().isoformat(),
                    'original_transaction': self.current_transaction,
                    'account_category': selected_account['category'],
                    'insights_generated': True
                }
            }

            self.processed_transactions.append(transaction)
            success_message = (
                f"Transaction recorded successfully!\n\n"
                f"Date: {transaction['date']}\n"
                f"Description: {transaction['description']}\n"
                f"Bank: {self.format_amount(amount)}\n"
                f"{selected_account['name']}: {self.format_amount(-amount)}\n\n"
                f"Transaction has been processed and insights have been generated."
            )

            return True, success_message, transaction

        except Exception as e:
            logger.error(f"Error completing transaction: {str(e)}")
            return False, f"Error processing transaction: {str(e)}", None