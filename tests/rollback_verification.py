import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import func
from flask import current_app
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
from models import User, Account, Transaction, UploadedFile, CompanySettings
from app import db
from utils.backup_manager import DatabaseBackupManager
from ai_utils import predict_account, suggest_explanation, find_similar_transactions

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

    def _test_with_backoff(self, test_func, test_name, max_retries=5, base_delay=2):
        """Helper method to run tests with improved exponential backoff and detailed logging"""
        last_error = None
        total_wait_time = 0
        
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                result = test_func()
                execution_time = time.time() - start_time
                
                self.logger.info(
                    f"{test_name} test successful on attempt {attempt + 1}\n"
                    f"Total wait time: {total_wait_time:.2f}s\n"
                    f"Execution time: {execution_time:.2f}s"
                )
                
                return {
                    'success': True,
                    'result': result,
                    'attempts': attempt + 1,
                    'total_wait_time': total_wait_time,
                    'execution_time': execution_time
                }
            except Exception as e:
                last_error = str(e)
                is_rate_limit = "rate limit" in str(e).lower()
                
                if is_rate_limit and attempt < max_retries - 1:
                    delay = min(base_delay * (2 ** attempt), 60)  # Cap at 60 seconds
                    total_wait_time += delay
                    
                    self.logger.info(
                        f"Rate limit hit for {test_name}\n"
                        f"Attempt: {attempt + 1}/{max_retries}\n"
                        f"Waiting: {delay}s\n"
                        f"Total wait time: {total_wait_time:.2f}s"
                    )
                    
                    time.sleep(delay)
                    continue
                
                error_type = "Rate limit" if is_rate_limit else "Execution"
                self.logger.warning(
                    f"{error_type} error in {test_name}\n"
                    f"Attempt: {attempt + 1}/{max_retries}\n"
                    f"Error: {str(e)}\n"
                    f"Total wait time: {total_wait_time:.2f}s"
                )
        
        return {
            'success': False,
            'error': last_error,
            'attempts': max_retries,
            'total_wait_time': total_wait_time
        }

    def verify_ai_features(self) -> bool:
        """
        Verifies AI features functionality with improved error handling and rate limiting
        """
        try:
            from ai_utils import predict_account, suggest_explanation, find_similar_transactions
            
            # Test data
            test_transaction = {
                'description': "Monthly office rent payment",
                'explanation': "Regular monthly payment for office space",
                'test_accounts': [
                    {'name': 'Rent Expense', 'category': 'Expenses', 'link': '510'},
                    {'name': 'Office Expenses', 'category': 'Expenses', 'link': '520'}
                ]
            }
            
            test_results = {
                'ASF': {'status': None, 'details': None},
                'ESF': {'status': None, 'details': None},
                'ERF': {'status': None, 'details': None}
            }
            
            # Test ASF
            def test_asf():
                result = predict_account(
                    test_transaction['description'],
                    test_transaction['explanation'],
                    test_transaction['test_accounts']
                )
                if not result:
                    raise ValueError("ASF returned no predictions")
                return result
            
            test_results['ASF'] = self._test_with_backoff(
                test_asf,
                "Account Suggestion Feature (ASF)"
            )
            
            # Test ESF
            def test_esf():
                result = suggest_explanation(test_transaction['description'])
                if not result or not result.get('suggested_explanation'):
                    raise ValueError("ESF returned no explanation")
                return result
            
            test_results['ESF'] = self._test_with_backoff(
                test_esf,
                "Explanation Suggestion Feature (ESF)"
            )
            
            # Test ERF
            def test_erf():
                result = find_similar_transactions(
                    test_transaction['description'],
                    [{'description': 'Office Rent Payment Q4', 'id': 1}]
                )
                if not result:
                    raise ValueError("ERF found no similar transactions")
                return result
            
            test_results['ERF'] = self._test_with_backoff(
                test_erf,
                "Explanation Recognition Feature (ERF)"
            )
            
            # Log detailed results
            for feature, result in test_results.items():
                if result['success']:
                    self.logger.info(
                        f"{feature} verification successful after {result['attempts']} attempt(s)"
                    )
                else:
                    self.logger.error(
                        f"{feature} verification failed after {result['attempts']} attempt(s): {result['error']}"
                    )
            
            # Verify all features working
            all_features_working = all(result['success'] for result in test_results.values())
            
            if all_features_working:
                self.logger.info("All AI features verified successfully")
                self.verification_results['ai_features'] = True
                return True
            else:
                failed_features = [f for f, r in test_results.items() if not r['success']]
                self.logger.error(f"AI features verification failed for: {', '.join(failed_features)}")
                return False
                
        except ImportError as ie:
            self.logger.error(f"AI utilities not available: {str(ie)}")
            return False
        except Exception as e:
            self.logger.error(f"Error verifying AI features: {str(e)}")
            return False
            
            # Already set in the previous block
            pass
    
    def verify_rate_limits(self, concurrent_requests=3) -> bool:
        """
        Verifies rate limit handling with parallel request processing and improved backoff
        
        Args:
            concurrent_requests: Number of concurrent requests to test with
        """
        try:
            from ai_utils import predict_account, suggest_explanation, find_similar_transactions
            
            # Test configuration
            max_retries = 3
            base_delay = 1
            test_requests = 5
            results = {
                'ASF': {'success': 0, 'rate_limits': 0},
                'ESF': {'success': 0, 'rate_limits': 0},
                'ERF': {'success': 0, 'rate_limits': 0}
            }
            
            test_data = {
                'description': "Monthly office rent payment",
                'explanation': "Regular monthly payment for office space",
                'accounts': [{'name': 'Rent Expense', 'category': 'Expenses', 'link': '510'}]
            }

            # Define test functions for each feature
            features_test = {
                'ASF': lambda: predict_account(
                    test_data['description'],
                    test_data['explanation'],
                    test_data['accounts']
                ),
                'ESF': lambda: suggest_explanation(test_data['description']),
                'ERF': lambda: find_similar_transactions(
                    test_data['description'],
                    [{'description': 'Similar rent payment', 'id': 1}]
                )
            }
            
            def run_feature_test(feature_name, test_func, request_id):
                result = self._test_with_backoff(
                    test_func,
                    f"{feature_name} (Request {request_id})"
                )
                
                if result['success']:
                    results[feature_name]['success'] += 1
                    self.logger.info(
                        f"{feature_name} request {request_id} succeeded\n"
                        f"Wait time: {result.get('total_wait_time', 0):.2f}s\n"
                        f"Execution time: {result.get('execution_time', 0):.2f}s"
                    )
                    return True
                else:
                    if "rate limit" in str(result.get('error', '')).lower():
                        results[feature_name]['rate_limits'] += 1
                    self.logger.error(
                        f"{feature_name} request {request_id} failed\n"
                        f"Error: {result.get('error')}\n"
                        f"Attempts: {result.get('attempts')}\n"
                        f"Total wait time: {result.get('total_wait_time', 0):.2f}s"
                    )
                    return False
            
            # Run tests in parallel with ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=concurrent_requests) as executor:
                for feature_name, test_func in features_test.items():
                    feature_futures = []
                    for request_id in range(test_requests):
                        future = executor.submit(
                            run_feature_test,
                            feature_name,
                            test_func,
                            request_id + 1
                        )
                        feature_futures.append(future)
                    
                    # Wait for all feature tests to complete
                    feature_results = [future.result() for future in as_completed(feature_futures)]
                    if not all(feature_results):
                        self.logger.error(f"One or more {feature_name} tests failed")
                        return False
                    
                    # Add small delay between features to prevent overwhelming the API
                    time.sleep(1)
                
                return True
            
            # Test each feature
            features_test = {
                'ASF': lambda: predict_account(
                    test_data['description'],
                    test_data['explanation'],
                    test_data['accounts']
                ),
                'ESF': lambda: suggest_explanation(test_data['description']),
                'ERF': lambda: find_similar_transactions(
                    test_data['description'],
                    [{'description': 'Similar rent payment', 'id': 1}]
                )
            }
            
            all_tests_passed = all(
                run_feature_test(name, func)
                for name, func in features_test.items()
            )
            
            if all_tests_passed:
                # Log detailed results
                for feature, counts in results.items():
                    success_rate = counts['success'] / test_requests * 100
                    self.logger.info(
                        f"{feature} Results: "
                        f"{counts['success']}/{test_requests} successful requests "
                        f"({success_rate:.1f}%), "
                        f"{counts['rate_limits']} rate limits handled"
                    )
                
                self.verification_results['rate_limits'] = True
                return True
            else:
                self.logger.error("One or more rate limit tests failed")
                return False
                
        except ImportError as ie:
            self.logger.error(f"AI utilities not available: {str(ie)}")
            return False
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
