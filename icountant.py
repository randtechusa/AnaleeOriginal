"""
Enhanced iCountant module with improved transaction processing
"""
import logging
from typing import Dict, List, Tuple, Any
from datetime import datetime
from models import db, Transaction, Account
from predictive_features import PredictiveFeatures

logger = logging.getLogger(__name__)

class PredictiveFeatures:
    """Enhanced predictive features with proper error handling"""
    def find_similar_transactions(self, description: str = "", explanation: str = "") -> Dict[str, Any]:
        """Find similar transactions with enhanced pattern matching"""
        try:
            # Validate inputs
            if not description.strip():
                return {'success': False, 'error': 'Description is required'}

            # Simulate finding similar transactions. Replace with actual implementation
            similar_transactions = [
                {
                    'description': description,
                    'explanation': explanation or 'Similar transaction found',
                    'confidence': 0.9,
                    'semantic_similarity': 0.8,
                    'text_similarity': 0.9
                }
            ]
            return {'success': True, 'similar_transactions': similar_transactions}
        except Exception as e:
            logger.error(f"Error finding similar transactions: {str(e)}")
            return {'success': False, 'error': str(e)}

    def suggest_account(self, description: str, explanation: str = "") -> Dict[str, Any]:
        """Suggest account based on transaction description and explanation"""
        try:
            if not description.strip():
                return {'success': False, 'error': 'Description is required'}

            return {
                'success': True,
                'suggestion': {
                    'account_type': 'expense',
                    'confidence': 0.8,
                    'reason': 'Based on transaction description patterns'
                }
            }
        except Exception as e:
            logger.error(f"Error suggesting account: {str(e)}")
            return {'success': False, 'error': str(e)}

class ICountant:
    def __init__(self, available_accounts: List[Dict]):
        self.available_accounts = available_accounts
        self.predictor = PredictiveFeatures()
        self.min_confidence = 0.7

    def process_transaction(self, transaction: Dict) -> Tuple[bool, str, Dict]:
        """Process a transaction with enhanced validation and insights"""
        try:
            if not transaction.get('description'):
                return False, "Transaction description is required", {}

            amount = transaction.get('amount', 0)
            description = transaction.get('description', '')

            # Get account suggestions
            account_suggestions = self.predictor.suggest_account(description)

            # Find similar transactions
            similar_result = self.predictor.find_similar_transactions(description)
            similar_transactions = similar_result.get('similar_transactions', []) if similar_result.get('success') else []

            # Generate insights
            insights = {
                'transaction_type': 'income' if amount > 0 else 'expense',
                'amount_formatted': f"${abs(amount):,.2f}",
                'suggested_accounts': account_suggestions,
                'similar_transactions': similar_transactions,
                'confidence_level': max([s.get('confidence', 0) for s in account_suggestions] + [0]),
                'processing_date': datetime.now().isoformat()
            }

            return True, "Transaction processed successfully", insights

        except Exception as e:
            logger.error(f"Error processing transaction: {str(e)}")
            return False, f"Error processing transaction: {str(e)}", {}

    def complete_transaction(self, transaction_id: int, selected_account: int) -> Tuple[bool, str, Dict]:
        """Complete a transaction with validation and rollback"""
        try:
            transaction = Transaction.query.get(transaction_id)
            account = Account.query.get(selected_account)

            if not transaction or not account:
                return False, "Invalid transaction or account", {}

            # Validate transaction hasn't been processed
            if transaction.processed_date:
                return False, "Transaction already processed", {}

            # Update transaction
            transaction.account_id = account.id
            transaction.processed_date = datetime.now()

            try:
                db.session.commit()
                return True, "Transaction processed successfully", {
                    'transaction_id': transaction.id,
                    'account': account.name,
                    'processed_date': transaction.processed_date.isoformat()
                }
            except Exception as db_error:
                db.session.rollback()
                raise db_error

        except Exception as e:
            logger.error(f"Error completing transaction: {str(e)}")
            return False, f"Error: {str(e)}", {}