import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from decimal import Decimal, InvalidOperation

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ICountant:
    """
    AI-powered accounting assistant for guided double-entry transaction processing
    """
    def __init__(self, available_accounts: List[Dict]):
        self.available_accounts = available_accounts
        self.current_transaction = None
        self.processed_transactions = []

    def validate_amount(self, amount) -> Tuple[bool, Optional[Decimal], str]:
        """Validate transaction amount"""
        try:
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
            # Validate transaction data
            if not isinstance(transaction, dict):
                return "Invalid transaction data format", None

            # Validate and convert amount
            is_valid, amount, message = self.validate_amount(transaction.get('amount'))
            if not is_valid:
                return message, None

            self.current_transaction = transaction

            # Bank account is the default first entry
            bank_entry = {
                'account': 'Bank',
                'amount': amount,
                'description': transaction.get('description', 'No description provided'),
                'date': transaction.get('date', datetime.now())
            }

            # Determine if we need debit or credit counterpart based on bank entry
            if amount > 0:  # Money received (bank debit)
                message = (
                    f"Transaction: {transaction.get('description', 'No description')}\n"
                    f"Amount: {self.format_amount(amount)}\n"
                    f"Bank account has been debited. Which account should receive the credit?\n\n"
                    f"Available Accounts:\n{self.get_account_options()}\n"
                    f"Please select the account number for the credit entry."
                )
                entry_type = 'credit'
            else:  # Money paid out (bank credit)
                message = (
                    f"Transaction: {transaction.get('description', 'No description')}\n"
                    f"Amount: {self.format_amount(amount)}\n"
                    f"Bank account has been credited. Which account should receive the debit?\n\n"
                    f"Available Accounts:\n{self.get_account_options()}\n"
                    f"Please select the account number for the debit entry."
                )
                entry_type = 'debit'

            return message, {
                'bank_entry': bank_entry,
                'entry_type_needed': entry_type,
                'original_transaction': transaction
            }

        except Exception as e:
            logger.error(f"Error processing transaction: {str(e)}")
            return f"Error processing transaction: {str(e)}", None

    def complete_transaction(self, selected_account_index: int) -> Tuple[bool, str, Optional[Dict]]:
        """
        Complete the transaction with the selected account
        Returns: (success, message, completed_transaction)
        """
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
                    'account_category': selected_account['category']
                }
            }

            self.processed_transactions.append(transaction)
            success_message = (
                f"Transaction recorded:\n"
                f"Date: {transaction['date']}\n"
                f"Description: {transaction['description']}\n"
                f"Bank: {self.format_amount(amount)}\n"
                f"{selected_account['name']}: {self.format_amount(-amount)}"
            )

            return True, success_message, transaction

        except Exception as e:
            logger.error(f"Error completing transaction: {str(e)}")
            return False, f"Error processing transaction: {str(e)}", None