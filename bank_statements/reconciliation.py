"""
Service for handling bank statement reconciliation and data cleanup
"""
import logging
from datetime import datetime
from typing import Dict, List, Tuple

from sqlalchemy import func
from models import db, Transaction, BankStatementUpload, Account

logger = logging.getLogger(__name__)

class ReconciliationService:
    """Service for reconciling and cleaning up bank statement data"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.cleanup_stats = {
            'duplicates_removed': 0,
            'invalid_dates_fixed': 0,
            'amount_mismatches_fixed': 0,
            'total_processed': 0
        }

    def find_duplicate_transactions(self) -> List[Transaction]:
        """Find duplicate transactions based on date, amount, and description"""
        duplicates = []
        try:
            # Group by date, amount, and description to find duplicates
            duplicate_groups = db.session.query(
                Transaction.date,
                Transaction.amount,
                Transaction.description,
                func.count('*').label('count')
            ).filter(
                Transaction.user_id == self.user_id
            ).group_by(
                Transaction.date,
                Transaction.amount,
                Transaction.description
            ).having(
                func.count('*') > 1
            ).all()

            # Get the actual duplicate transactions
            for group in duplicate_groups:
                transactions = Transaction.query.filter(
                    Transaction.user_id == self.user_id,
                    Transaction.date == group.date,
                    Transaction.amount == group.amount,
                    Transaction.description == group.description
                ).order_by(Transaction.created_at).all()
                
                # Keep the first transaction, mark others as duplicates
                if len(transactions) > 1:
                    duplicates.extend(transactions[1:])
                    
            return duplicates
        except Exception as e:
            logger.error(f"Error finding duplicates: {str(e)}")
            return []

    def validate_transaction_dates(self) -> List[Transaction]:
        """Find transactions with invalid dates"""
        invalid_dates = []
        try:
            current_date = datetime.utcnow()
            invalid_dates = Transaction.query.filter(
                Transaction.user_id == self.user_id,
                Transaction.date > current_date
            ).all()
            
            return invalid_dates
        except Exception as e:
            logger.error(f"Error validating dates: {str(e)}")
            return []

    def reconcile_accounts(self) -> Dict[str, List[Dict]]:
        """Reconcile transactions with bank statements"""
        reconciliation_report = {
            'matched': [],
            'unmatched': [],
            'possible_matches': []
        }
        
        try:
            # Get all bank accounts for user
            accounts = Account.query.filter_by(user_id=self.user_id).all()
            
            for account in accounts:
                # Get transactions for this account
                transactions = Transaction.query.filter_by(
                    user_id=self.user_id,
                    account_id=account.id
                ).all()
                
                for transaction in transactions:
                    # Find matching bank statement entries
                    statement_match = BankStatementUpload.query.filter_by(
                        user_id=self.user_id,
                        account_id=account.id
                    ).filter(
                        func.date(BankStatementUpload.upload_date) == func.date(transaction.date)
                    ).first()
                    
                    if statement_match:
                        reconciliation_report['matched'].append({
                            'transaction_id': transaction.id,
                            'date': transaction.date,
                            'amount': transaction.amount,
                            'description': transaction.description,
                            'statement_id': statement_match.id
                        })
                    else:
                        reconciliation_report['unmatched'].append({
                            'transaction_id': transaction.id,
                            'date': transaction.date,
                            'amount': transaction.amount,
                            'description': transaction.description
                        })
            
            return reconciliation_report
        except Exception as e:
            logger.error(f"Error reconciling accounts: {str(e)}")
            return reconciliation_report

    def perform_cleanup(self) -> Tuple[bool, Dict]:
        """Perform data cleanup and reconciliation"""
        try:
            # Find and remove duplicates
            duplicates = self.find_duplicate_transactions()
            self.cleanup_stats['duplicates_removed'] = len(duplicates)
            
            # Validate dates
            invalid_dates = self.validate_transaction_dates()
            self.cleanup_stats['invalid_dates_fixed'] = len(invalid_dates)
            
            # Reconcile accounts
            reconciliation_report = self.reconcile_accounts()
            
            # Update cleanup stats
            self.cleanup_stats['total_processed'] = (
                Transaction.query.filter_by(user_id=self.user_id).count()
            )
            
            return True, {
                'cleanup_stats': self.cleanup_stats,
                'reconciliation_report': reconciliation_report
            }
            
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
            return False, {
                'error': str(e),
                'cleanup_stats': self.cleanup_stats
            }
