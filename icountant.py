import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from decimal import Decimal, InvalidOperation
from ai_insights import FinancialInsightsGenerator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ICountant:
    """
    AI-powered accounting assistant for guided double-entry transaction processing
    with real-time insights and pattern recognition
    """
    def __init__(self, available_accounts: List[Dict]):
        self.available_accounts = available_accounts
        self.current_transaction = None
        self.processed_transactions = []
        self.insights_generator = FinancialInsightsGenerator()

    def get_transaction_insights(self, transaction: Dict) -> Dict:
        """Generate AI-powered insights for the current transaction"""
        try:
            # Get similar transactions from history
            similar_transactions = [t for t in self.processed_transactions 
                                 if abs(t['entries'][0]['debit'] - abs(transaction['amount'])) < 100]

            # Generate insights using AI
            insights = self.insights_generator.generate_transaction_insights([transaction])

            # Suggest accounts based on description and amount
            suggested_accounts = self._suggest_accounts(transaction)

            return {
                'similar_transactions': similar_transactions[:3],
                'ai_insights': insights.get('insights', ''),
                'suggested_accounts': suggested_accounts,
                'transaction_type': 'credit' if transaction['amount'] < 0 else 'debit',
                'amount_formatted': self.format_amount(Decimal(str(transaction['amount'])))
            }
        except Exception as e:
            logger.error(f"Error generating transaction insights: {str(e)}")
            return {}

    def _suggest_accounts(self, transaction: Dict) -> List[Dict]:
        """Suggest relevant accounts based on transaction details"""
        try:
            amount = Decimal(str(transaction['amount']))
            is_income = amount > 0

            # Filter accounts based on transaction type
            suggested = []
            for account in self.available_accounts:
                # For positive amounts (income), suggest revenue accounts
                if is_income and account['category'].lower() in ['revenue', 'income', 'sales']:
                    suggested.append({
                        'account': account,
                        'confidence': 0.8,
                        'reason': 'Common income account'
                    })
                # For negative amounts (expenses), suggest expense accounts
                elif not is_income and account['category'].lower() in ['expense', 'expenses', 'cost']:
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
            if amount is None:
                return False, None, "Amount cannot be None"

            decimal_amount = Decimal(str(amount))
            if decimal_amount == 0:
                return False, None, "Transaction amount cannot be zero"
            return True, decimal_amount, "Amount validated successfully"
        except (InvalidOperation, TypeError, ValueError) as e:
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

    def process_transaction(self, transaction: Dict) -> Tuple[str, Optional[Dict]]:
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
            is_valid, amount, message = self.validate_amount(transaction.get('amount'))
            if not is_valid:
                return message, None

            self.current_transaction = transaction

            # Generate insights for the transaction
            transaction_insights = self.get_transaction_insights(transaction)

            # Bank account is the default first entry
            bank_entry = {
                'account': 'Bank',
                'amount': amount,
                'description': transaction.get('description', 'No description provided'),
                'date': transaction.get('date', datetime.now())
            }

            # Build guidance message with insights
            if amount > 0:  # Money received (bank debit)
                message = (
                    f"Transaction Analysis:\n"
                    f"Description: {transaction.get('description', 'No description')}\n"
                    f"Amount: {self.format_amount(amount)}\n"
                    f"Type: Income/Revenue Transaction\n\n"
                    f"AI Insights:\n{transaction_insights.get('ai_insights', 'No insights available')}\n\n"
                    f"Suggested Accounts:\n"
                )
                for suggestion in transaction_insights.get('suggested_accounts', []):
                    message += f"- {suggestion['account']['name']} ({suggestion['reason']})\n"

                message += f"\nAvailable Accounts:\n{self.get_account_options()}\n"
                message += f"Please select the account number for the credit entry."
                entry_type = 'credit'
            else:  # Money paid out (bank credit)
                message = (
                    f"Transaction Analysis:\n"
                    f"Description: {transaction.get('description', 'No description')}\n"
                    f"Amount: {self.format_amount(amount)}\n"
                    f"Type: Expense/Payment Transaction\n\n"
                    f"AI Insights:\n{transaction_insights.get('ai_insights', 'No insights available')}\n\n"
                    f"Suggested Accounts:\n"
                )
                for suggestion in transaction_insights.get('suggested_accounts', []):
                    message += f"- {suggestion['account']['name']} ({suggestion['reason']})\n"

                message += f"\nAvailable Accounts:\n{self.get_account_options()}\n"
                message += f"Please select the account number for the debit entry."
                entry_type = 'debit'

            return message, {
                'bank_entry': bank_entry,
                'entry_type_needed': entry_type,
                'original_transaction': transaction,
                'insights': transaction_insights
            }

        except Exception as e:
            logger.error(f"Error processing transaction: {str(e)}")
            return f"Error processing transaction: {str(e)}", None

    def complete_transaction(self, selected_account_index: int) -> Tuple[bool, str, Optional[Dict]]:
        """Complete the transaction with the selected account"""
        if not self.current_transaction:
            return False, "No transaction in progress", None

        try:
            if not (0 <= selected_account_index < len(self.available_accounts)):
                return False, "Invalid account selection", None

            selected_account = self.available_accounts[selected_account_index]
            amount = Decimal(str(self.current_transaction['amount']))

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