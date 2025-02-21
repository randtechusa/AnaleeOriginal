
"""
Enhanced iCountant module with improved transaction processing and validation
"""
import logging
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime
from decimal import Decimal
from models import db, Transaction, Account
from predictive_features import PredictiveFeatures

logger = logging.getLogger(__name__)

class TransactionValidator:
    """Validates transaction data"""
    @staticmethod
    def validate_transaction(transaction: Dict) -> Tuple[bool, str]:
        if not isinstance(transaction, dict):
            return False, "Invalid transaction format"
        
        required_fields = ['description', 'amount']
        for field in required_fields:
            if field not in transaction:
                return False, f"Missing required field: {field}"
                
        if not isinstance(transaction.get('amount'), (int, float, Decimal)):
            return False, "Invalid amount format"
            
        return True, "Transaction validated"

class ICountant:
    """Enhanced ICountant with comprehensive validation and error handling"""
    
    def __init__(self, available_accounts: List[Dict]):
        self.available_accounts = available_accounts
        self.predictor = PredictiveFeatures()
        self.validator = TransactionValidator()
        self.min_confidence = 0.7
        self.setup_logging()

    def setup_logging(self):
        """Configure logging for ICountant"""
        handler = logging.FileHandler('icountant.log')
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    def process_transaction(self, transaction: Dict) -> Tuple[bool, str, Dict]:
        """Process a transaction with enhanced validation and insights"""
        try:
            # Validate transaction
            is_valid, validation_message = self.validator.validate_transaction(transaction)
            if not is_valid:
                logger.error(f"Transaction validation failed: {validation_message}")
                return False, validation_message, {}

            description = transaction.get('description', '').strip()
            amount = Decimal(str(transaction.get('amount', 0)))
            
            # Get account suggestions
            account_suggestions = self.predictor.suggest_account(description)
            
            # Find similar transactions
            similar_result = self.predictor.find_similar_transactions(description)
            similar_transactions = similar_result.get('similar_transactions', []) if similar_result.get('success') else []

            # Generate detailed insights
            insights = {
                'transaction_type': 'income' if amount > 0 else 'expense',
                'amount_formatted': f"${abs(amount):,.2f}",
                'suggested_accounts': account_suggestions,
                'similar_transactions': similar_transactions,
                'confidence_level': max([s.get('confidence', 0) for s in account_suggestions] + [0]),
                'processing_date': datetime.now().isoformat(),
                'patterns': {
                    'frequency': self._analyze_frequency(description, similar_transactions),
                    'amount_pattern': self._analyze_amount_pattern(amount, similar_transactions),
                    'timing_pattern': self._analyze_timing_pattern(similar_transactions)
                }
            }

            logger.info(f"Transaction processed successfully: {description}")
            return True, "Transaction processed successfully", insights

        except Exception as e:
            logger.error(f"Error processing transaction: {str(e)}", exc_info=True)
            return False, f"Error processing transaction: {str(e)}", {}

    def complete_transaction(self, transaction_id: int, selected_account: int) -> Tuple[bool, str, Dict]:
        """Complete a transaction with enhanced validation and rollback handling"""
        try:
            # Validate inputs
            if not transaction_id or not selected_account:
                return False, "Invalid transaction or account ID", {}

            # Get transaction and account
            transaction = Transaction.query.get(transaction_id)
            account = Account.query.get(selected_account)

            if not transaction or not account:
                logger.error(f"Invalid transaction ({transaction_id}) or account ({selected_account})")
                return False, "Invalid transaction or account", {}

            # Validate transaction hasn't been processed
            if transaction.processed_date:
                logger.warning(f"Transaction {transaction_id} already processed")
                return False, "Transaction already processed", {
                    'processed_date': transaction.processed_date.isoformat()
                }

            # Update transaction with retry mechanism
            retry_count = 0
            max_retries = 3
            while retry_count < max_retries:
                try:
                    transaction.account_id = account.id
                    transaction.processed_date = datetime.now()
                    db.session.commit()

                    logger.info(f"Transaction {transaction_id} completed successfully")
                    return True, "Transaction processed successfully", {
                        'transaction_id': transaction.id,
                        'account': account.name,
                        'processed_date': transaction.processed_date.isoformat(),
                        'amount': float(transaction.amount) if transaction.amount else 0
                    }

                except Exception as db_error:
                    retry_count += 1
                    logger.warning(f"Retry {retry_count} for transaction {transaction_id}: {str(db_error)}")
                    db.session.rollback()
                    if retry_count == max_retries:
                        raise db_error

        except Exception as e:
            logger.error(f"Error completing transaction: {str(e)}", exc_info=True)
            return False, f"Error: {str(e)}", {}

    def _analyze_frequency(self, description: str, similar_transactions: List[Dict]) -> Dict:
        """Analyze transaction frequency patterns"""
        try:
            total_similar = len(similar_transactions)
            if total_similar == 0:
                return {'pattern': 'new', 'confidence': 1.0}

            monthly_count = sum(1 for t in similar_transactions if 'monthly' in t.get('description', '').lower())
            if monthly_count > total_similar * 0.5:
                return {'pattern': 'monthly', 'confidence': monthly_count/total_similar}

            return {'pattern': 'irregular', 'confidence': 0.8}
        except Exception as e:
            logger.error(f"Error analyzing frequency: {str(e)}")
            return {'pattern': 'unknown', 'confidence': 0}

    def _analyze_amount_pattern(self, amount: Decimal, similar_transactions: List[Dict]) -> Dict:
        """Analyze transaction amount patterns"""
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
        """Analyze transaction timing patterns"""
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
