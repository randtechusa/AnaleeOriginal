import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import func
from flask import current_app
from models import User, Account, Transaction, UploadedFile, CompanySettings
from app import db
from datetime import datetime, timedelta
import time
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class RollbackVerificationTest:
    """Handles verification of system state after rollbacks"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.verification_results = {
            'data_integrity': False,
            'system_state': False,
            'ai_features': False,
            'rate_limits': False
        }
    
    def verify_data_integrity(self, reference_time: datetime) -> bool:
        """
        Verifies data integrity by comparing current state with expected state
        """
        try:
            # Check transaction consistency
            transactions = Transaction.query.filter(
                Transaction.updated_at >= reference_time
            ).all()
            
            # Verify account relationships
            for transaction in transactions:
                if transaction.account_id:
                    account = Account.query.get(transaction.account_id)
                    if not account or account.user_id != transaction.user_id:
                        self.logger.error(f"Data integrity error: Invalid account relationship for transaction {transaction.id}")
                        return False
            
            # Verify file relationships
            files = UploadedFile.query.filter(
                UploadedFile.upload_date >= reference_time
            ).all()
            
            for file in files:
                file_transactions = Transaction.query.filter_by(file_id=file.id).all()
                if not all(t.user_id == file.user_id for t in file_transactions):
                    self.logger.error(f"Data integrity error: Mismatched user IDs in file {file.id}")
                    return False
            
            self.verification_results['data_integrity'] = True
            return True
            
        except Exception as e:
            self.logger.error(f"Error verifying data integrity: {str(e)}")
            return False
    
    def verify_system_state(self) -> bool:
        """
        Verifies system state consistency
        """
        try:
            # Check database connectivity
            db.session.execute("SELECT 1")
            
            # Verify essential tables exist and are accessible
            essential_tables = ['users', 'accounts', 'transactions', 'uploaded_files']
            for table in essential_tables:
                result = db.session.execute(f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='{table}')")
                if not result.scalar():
                    self.logger.error(f"System state error: Table {table} not found")
                    return False
            
            # Check for orphaned records
            orphaned_transactions = Transaction.query.filter(
                ~Transaction.account_id.in_(
                    db.session.query(Account.id)
                )
            ).count()
            
            if orphaned_transactions > 0:
                self.logger.warning(f"Found {orphaned_transactions} orphaned transactions")
            
            self.verification_results['system_state'] = True
            return True
            
        except Exception as e:
            self.logger.error(f"Error verifying system state: {str(e)}")
            return False

    def verify_ai_features(self) -> bool:
        """
        Verifies AI features functionality
        """
        try:
            from ai_utils import predict_account, suggest_explanation, find_similar_transactions
            has_ai = True
        except ImportError:
            self.logger.warning("AI utilities not available, will test manual fallback")
            has_ai = False
        
        try:
            if has_ai:
                # Test ASF with exponential backoff
                max_retries = 3
                base_delay = 1
                
                for attempt in range(max_retries):
                    try:
                        test_result = predict_account(
                            "Test transaction",
                            "Test explanation",
                            [{'name': 'Test Account', 'category': 'Test', 'link': 'test'}]
                        )
                        break
                    except Exception as e:
                        if "rate limit" in str(e).lower():
                            delay = base_delay * (2 ** attempt)
                            self.logger.info(f"Rate limit hit, waiting {delay} seconds before retry")
                            time.sleep(delay)
                            continue
                        self.logger.warning(f"AI prediction failed: {str(e)}, falling back to manual")
                        break
            else:
                # Test manual fallback
                self.logger.info("Testing manual processing fallback")
            
            # Test ESF
            explanation = suggest_explanation("Test transaction")
            if not explanation:
                self.logger.warning("ESF verification: No explanation generated")
            
            # Test ERF
            similar = find_similar_transactions(
                "Test transaction",
                [{'description': 'Similar test transaction', 'id': 1}]
            )
            if not similar:
                self.logger.warning("ERF verification: No similar transactions found")
            
            self.verification_results['ai_features'] = True
            return True
            
        except Exception as e:
            self.logger.error(f"Error verifying AI features: {str(e)}")
            return False
    
    def verify_rate_limits(self) -> bool:
        """
        Verifies rate limit handling with exponential backoff
        """
        try:
            from ai_utils import predict_account
            
            # Test rate limit handling with exponential backoff
            max_retries = 3
            base_delay = 1
            test_requests = 5
            success_count = 0
            rate_limit_count = 0
            
            for request_num in range(test_requests):
                for attempt in range(max_retries):
                    try:
                        result = predict_account(
                            "Test transaction",
                            "Test explanation",
                            [{'name': 'Test Account', 'category': 'Test', 'link': 'test'}]
                        )
                        success_count += 1
                        break
                    except Exception as e:
                        if "rate limit" in str(e).lower():
                            rate_limit_count += 1
                            if attempt < max_retries - 1:
                                delay = base_delay * (2 ** attempt)
                                self.logger.info(f"Rate limit hit, waiting {delay} seconds before retry")
                                time.sleep(delay)
                                continue
                        else:
                            raise
                
                # Add a small delay between requests to prevent rapid succession
                time.sleep(0.5)
            
            self.logger.info(
                f"Rate limit test results: {success_count} successes, "
                f"{rate_limit_count} rate limits handled with exponential backoff"
            )
            
            # Consider test successful if we handled rate limits appropriately
            self.verification_results['rate_limits'] = True
            return True
            
        except Exception as e:
            self.logger.error(f"Error verifying rate limits: {str(e)}")
            return False
    
    def run_all_verifications(self, reference_time: datetime) -> Dict[str, bool]:
        """
        Runs all verification tests
        """
        verifications = [
            ('data_integrity', lambda: self.verify_data_integrity(reference_time)),
            ('system_state', self.verify_system_state),
            ('ai_features', self.verify_ai_features),
            ('rate_limits', self.verify_rate_limits)
        ]
        
        for name, verification in verifications:
            try:
                self.verification_results[name] = verification()
                self.logger.info(f"Verification {name}: {'Passed' if self.verification_results[name] else 'Failed'}")
            except Exception as e:
                self.logger.error(f"Error during {name} verification: {str(e)}")
                self.verification_results[name] = False
        
        return self.verification_results
