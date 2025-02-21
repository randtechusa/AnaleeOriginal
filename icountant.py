"""
Enhanced iCountant module with improved transaction processing and validation
"""
import logging
import time
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime
from decimal import Decimal, InvalidOperation
from models import db, Transaction, Account
from predictive_features import PredictiveFeatures

logger = logging.getLogger(__name__)

class TransactionValidator:
    """Validates transaction data"""
    @staticmethod
    def validate_transaction(transaction: Dict) -> Tuple[bool, str]:
        if not isinstance(transaction, dict):
            return False, "Invalid transaction format"

        required_fields = ['description', 'amount', 'date']
        missing_fields = [field for field in required_fields if field not in transaction]
        if missing_fields:
            return False, f"Missing required fields: {', '.join(missing_fields)}"

        try:
            amount = Decimal(str(transaction['amount']))
            if amount == 0:
                return False, "Amount cannot be zero"
        except (InvalidOperation, ValueError):
            return False, "Invalid amount format"

        try:
            if isinstance(transaction['date'], str):
                datetime.strptime(transaction['date'], '%Y-%m-%d')
        except ValueError:
            return False, "Invalid date format (use YYYY-MM-DD)"

        if not transaction.get('description', '').strip():
            return False, "Description cannot be empty"

        return True, "Transaction validated"

class ICountant:
    def __init__(self, available_accounts: List[Dict]):
        self.available_accounts = available_accounts or []
        self.predictor = PredictiveFeatures()
        self.validator = TransactionValidator()
        self.setup_logging()
        # Placeholder for historical transactions - needs proper implementation
        self.historical_transactions = []

    def setup_logging(self):
        handler = logging.FileHandler('icountant.log')
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    def process_transaction(self, transaction: Dict) -> Tuple[bool, str, Dict]:
        """Process transaction with enhanced AI insights"""
        try:
            amount = transaction.get('amount', 0)
            description = transaction.get('description', '')

            # Generate insights
            transaction_info = {
                'insights': {
                    'amount_formatted': f"${abs(amount):,.2f}",
                    'transaction_type': 'income' if amount > 0 else 'expense',
                    'ai_insights': self._generate_insights(description, amount),
                    'suggested_accounts': self._suggest_accounts(description, amount),
                }
            }

            message = "Transaction analyzed successfully"
            return True, message, transaction_info

        except Exception as e:
            return False, str(e), {}

    def _generate_insights(self, description, amount):
        """Generate AI-powered insights"""
        insights = f"<div class='alert alert-info'>"
        insights += f"<i class='fas fa-robot me-2'></i>"
        insights += f"Transaction appears to be a {self._categorize_transaction(description)}"
        insights += "</div>"
        return insights

    def _suggest_accounts(self, description, amount):
        """Suggest appropriate accounts"""
        suggestions = []
        for account in self.available_accounts:
            if self._matches_account(description, account):
                suggestions.append({
                    'account': account,
                    'reason': f"Matches typical {account['category']} transaction pattern"
                })
        return suggestions[:3]  # Return top 3 suggestions

    def _categorize_transaction(self, description: str) -> str:
        # Placeholder for more sophisticated categorization logic
        if "rent" in description.lower():
            return "rent payment"
        elif "grocery" in description.lower():
            return "grocery purchase"
        elif "salary" in description.lower():
            return "salary deposit"
        else:
            return "uncategorized transaction"

    def _matches_account(self, description: str, account: Dict) -> bool:
        # Placeholder for more robust matching logic
        return any(keyword in description.lower() for keyword in account.get('keywords', []))

    def complete_transaction(self, transaction_id: int, selected_account: int) -> Tuple[bool, str, Dict]:
        try:
            if not isinstance(transaction_id, int) or not isinstance(selected_account, int):
                return False, "Invalid transaction or account ID", {}

            transaction = Transaction.query.get(transaction_id)
            account = Account.query.get(selected_account)

            if not transaction or not account:
                logger.error(f"Invalid transaction ({transaction_id}) or account ({selected_account})")
                return False, "Invalid transaction or account", {}

            if transaction.processed_date:
                logger.warning(f"Transaction {transaction_id} already processed")
                return False, "Transaction already processed", {
                    'processed_date': transaction.processed_date.isoformat()
                }

            retry_count = 0
            max_retries = 3
            while retry_count < max_retries:
                try:
                    transaction.account_id = account.id
                    transaction.processed_date = datetime.now()
                    db.session.commit()
                    break
                except Exception as db_error:
                    retry_count += 1
                    logger.warning(f"Retry {retry_count} for transaction {transaction_id}: {str(db_error)}")
                    db.session.rollback()
                    if retry_count == max_retries:
                        raise db_error

            logger.info(f"Transaction {transaction_id} completed successfully")
            return True, "Transaction processed successfully", {
                'transaction_id': transaction.id,
                'account': account.name,
                'processed_date': transaction.processed_date.isoformat(),
                'amount': float(transaction.amount) if transaction.amount else 0
            }

        except Exception as e:
            logger.error(f"Error completing transaction: {str(e)}", exc_info=True)
            return False, f"Error: {str(e)}", {}

    def _analyze_frequency(self, description: str, similar_transactions: List[Dict]) -> Dict:
        try:
            total_similar = len(similar_transactions)
            if total_similar == 0:
                return {'pattern': 'new', 'confidence': 1.0}

            monthly_count = sum(1 for t in similar_transactions 
                              if 'monthly' in t.get('description', '').lower())
            if monthly_count > total_similar * 0.5:
                return {'pattern': 'monthly', 'confidence': monthly_count/total_similar}

            return {'pattern': 'irregular', 'confidence': 0.8}
        except Exception as e:
            logger.error(f"Error analyzing frequency: {str(e)}")
            return {'pattern': 'unknown', 'confidence': 0}

    def _analyze_amount_pattern(self, amount: Decimal, similar_transactions: List[Dict]) -> Dict:
        try:
            if not similar_transactions:
                return {'pattern': 'unique', 'confidence': 1.0}

            amounts = [Decimal(str(t.get('amount', 0))) for t in similar_transactions]
            avg_amount = sum(amounts) / len(amounts)
            variance = abs(amount - avg_amount) / avg_amount if avg_amount else 1

            if variance < 0.1:
                return {'pattern': 'consistent', 'confidence': 0.9}
            elif variance < 0.3:
                return {'pattern': 'similar', 'confidence': 0.7}
            else:
                return {'pattern': 'variable', 'confidence': 0.5}
        except Exception as e:
            logger.error(f"Error analyzing amount pattern: {str(e)}")
            return {'pattern': 'unknown', 'confidence': 0}

    def _analyze_timing_pattern(self, similar_transactions: List[Dict]) -> Dict:
        try:
            if not similar_transactions:
                return {'pattern': 'new', 'confidence': 1.0}

            dates = [datetime.fromisoformat(t['date']) for t in similar_transactions if t.get('date')]
            if not dates:
                return {'pattern': 'unknown', 'confidence': 0}

            days_between = [(dates[i] - dates[i+1]).days for i in range(len(dates)-1)]
            if not days_between:
                return {'pattern': 'single', 'confidence': 1.0}

            avg_days = sum(days_between) / len(days_between)
            if 25 <= avg_days <= 31:
                return {'pattern': 'monthly', 'confidence': 0.9}
            elif 6 <= avg_days <= 8:
                return {'pattern': 'weekly', 'confidence': 0.9}
            else:
                return {'pattern': 'irregular', 'confidence': 0.7}
        except Exception as e:
            logger.error(f"Error analyzing timing pattern: {str(e)}")
            return {'pattern': 'unknown', 'confidence': 0}