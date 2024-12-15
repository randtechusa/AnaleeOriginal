import logging
import time
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial

try:
    from sqlalchemy import func, text
    from flask import current_app
    from models import User, Account, Transaction, UploadedFile, CompanySettings
    from app import db
    from utils.backup_manager import DatabaseBackupManager
    from ai_utils import predict_account, suggest_explanation, find_similar_transactions
except ImportError as e:
    logging.error(f"Failed to import required modules: {str(e)}")
    raise

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
        
    def _safe_execute(self, func, feature_name: str) -> Dict[str, Any]:
        """
        Safely executes a test function with proper error handling and logging
        
        Args:
            func: The function to execute
            feature_name: Name of the feature being tested
            
        Returns:
            Dict containing execution results and metadata
        """
        try:
            start_time = time.time()
            result = func()
            execution_time = time.time() - start_time
            
            return {
                'success': True,
                'result': result,
                'execution_time': execution_time
            }
        except Exception as e:
            self.logger.error(f"Error executing {feature_name}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
    
    def verify_data_integrity(self, reference_time: datetime) -> bool:
        """
        Verifies data integrity by comparing current state with expected state
        Implements transaction support and detailed error logging
        """
        try:
            with db.session.begin():
                # Log verification start with reference time
                self.logger.info(f"Starting data integrity verification from {reference_time}")
                
                # Check transaction consistency with detailed logging
                self.logger.debug("Querying transactions after reference time")
                transactions = Transaction.query.filter(
                    Transaction.updated_at >= reference_time
                ).all()
                self.logger.info(f"Found {len(transactions)} transactions to verify")
                
                # Verify account relationships with detailed status
                for transaction in transactions:
                    self.logger.debug(f"Verifying transaction {transaction.id}")
                    if transaction.account_id:
                        account = Account.query.get(transaction.account_id)
                        if not account:
                            self.logger.error(f"Data integrity error: Account {transaction.account_id} not found for transaction {transaction.id}")
                            return False
                        if account.user_id != transaction.user_id:
                            self.logger.error(
                                f"Data integrity error: User mismatch for transaction {transaction.id}. "
                                f"Transaction user: {transaction.user_id}, Account user: {account.user_id}"
                            )
                            return False
                
                # Verify file relationships with improved logging
                self.logger.debug("Querying uploaded files after reference time")
                files = UploadedFile.query.filter(
                    UploadedFile.upload_date >= reference_time
                ).all()
                self.logger.info(f"Found {len(files)} files to verify")
                
                for file in files:
                    self.logger.debug(f"Verifying file {file.id} relationships")
                    file_transactions = Transaction.query.filter_by(file_id=file.id).all()
                    if not file_transactions:
                        self.logger.warning(f"No transactions found for file {file.id}")
                        continue
                        
                    mismatched_transactions = [
                        t.id for t in file_transactions 
                        if t.user_id != file.user_id
                    ]
                    if mismatched_transactions:
                        self.logger.error(
                            f"Data integrity error: Mismatched user IDs in file {file.id}. "
                            f"Affected transactions: {mismatched_transactions}"
                        )
                        return False
                
                self.logger.info("Data integrity verification completed successfully")
                self.verification_results['data_integrity'] = True
                return True
            
        except Exception as e:
            self.logger.error(f"Error verifying data integrity: {str(e)}", exc_info=True)
            return False
    
    def verify_system_state(self) -> bool:
        """
        Verifies system state consistency with comprehensive checks
        and improved error handling
        """
        try:
            self.logger.info("Starting system state verification")
            
            # Check database connectivity with timeout
            try:
                db.session.execute(text("SELECT 1")).scalar()
                self.logger.debug("Database connection verified")
            except Exception as db_error:
                self.logger.error(f"Database connectivity test failed: {str(db_error)}")
                return False
            
            # Verify essential tables with detailed schema check
            essential_tables = {
                'users': ['id', 'username', 'email', 'password_hash'],
                'account': ['id', 'link', 'category', 'name', 'user_id'],
                'transactions': ['id', 'date', 'description', 'amount', 'user_id'],
                'uploaded_files': ['id', 'filename', 'upload_date', 'user_id']
            }
            
            for table, expected_columns in essential_tables.items():
                try:
                    # Check table existence
                    exists_query = text(
                        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                        "WHERE table_name=:table)"
                    )
                    exists = db.session.execute(exists_query, {"table": table}).scalar()
                    
                    if not exists:
                        self.logger.error(f"System state error: Table '{table}' not found")
                        return False
                    
                    # Verify column structure
                    columns_query = text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name=:table"
                    )
                    columns = [row[0] for row in db.session.execute(columns_query, {"table": table})]
                    
                    missing_columns = set(expected_columns) - set(columns)
                    if missing_columns:
                        self.logger.error(
                            f"System state error: Missing columns in '{table}': {missing_columns}"
                        )
                        return False
                    
                    self.logger.debug(f"Table '{table}' verified with expected structure")
                    
                except Exception as table_error:
                    self.logger.error(f"Error checking table '{table}': {str(table_error)}")
                    return False
            
            # Check for orphaned records with detailed reporting
            try:
                orphaned_queries = {
                    'transactions': text("""
                        SELECT COUNT(*) FROM transactions t
                        LEFT JOIN account a ON t.account_id = a.id
                        WHERE t.account_id IS NOT NULL AND a.id IS NULL
                    """),
                    'uploaded_files': text("""
                        SELECT COUNT(*) FROM uploaded_files f
                        LEFT JOIN users u ON f.user_id = u.id
                        WHERE u.id IS NULL
                    """)
                }
                
                for record_type, query in orphaned_queries.items():
                    count = db.session.execute(query).scalar()
                    if count > 0:
                        self.logger.warning(
                            f"Found {count} orphaned {record_type}. "
                            "This may indicate data inconsistency."
                        )
                
            except Exception as orphan_error:
                self.logger.error(f"Error checking orphaned records: {str(orphan_error)}")
                return False
            
            self.logger.info("System state verification completed successfully")
            self.verification_results['system_state'] = True
            return True
            
        except Exception as e:
            self.logger.error(f"Error verifying system state: {str(e)}", exc_info=True)
            return False

    def _test_with_backoff(self, test_func, test_name, max_retries=5, base_delay=2):
        """Helper method to run tests with improved exponential backoff and detailed logging"""
        last_error = None
        total_wait_time = 0
        jitter = 0.1  # Add jitter to prevent thundering herd
        
        for attempt in range(max_retries):
            try:
                # Add jitter to base delay
                jittered_delay = base_delay * (1 + random.uniform(-jitter, jitter))
                
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
        Verifies AI features functionality with improved error handling and rate limiting.
        Implements exponential backoff and detailed logging for API requests.
        """
        try:
            from ai_utils import predict_account, suggest_explanation, find_similar_transactions
            
            # Test data with more diverse scenarios
            test_transactions = [
                {
                    'description': "Monthly office rent payment",
                    'explanation': "Regular monthly payment for office space",
                    'test_accounts': [
                        {'name': 'Rent Expense', 'category': 'Expenses', 'link': '510'},
                        {'name': 'Office Expenses', 'category': 'Expenses', 'link': '520'}
                    ]
                },
                {
                    'description': "Utility bill payment",
                    'explanation': "Monthly electricity and water charges",
                    'test_accounts': [
                        {'name': 'Utilities', 'category': 'Expenses', 'link': '530'},
                        {'name': 'Operating Expenses', 'category': 'Expenses', 'link': '540'}
                    ]
                }
            ]
            
            test_results = {
                'ASF': {'status': None, 'details': None},
                'ESF': {'status': None, 'details': None},
                'ERF': {'status': None, 'details': None}
            }
            
            for test_transaction in test_transactions:
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
                    similar_transaction = {
                        'description': f"Previous {test_transaction['description']}",
                        'id': 1
                    }
                    result = find_similar_transactions(
                        test_transaction['description'],
                        [similar_transaction]
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
    
    def verify_rate_limits(self, concurrent_requests: int = 3, max_retries: int = 5) -> bool:
        """
        Verifies rate limit handling with parallel request processing and improved backoff
        
        Args:
            concurrent_requests: Number of concurrent requests to test with
            max_retries: Maximum number of retry attempts for rate-limited requests
            
        Returns:
            bool: True if all rate limit tests pass, False otherwise
        """
        self.logger.info(f"Starting rate limit verification tests with {concurrent_requests} concurrent requests")
        
        try:
            from ai_utils import predict_account, suggest_explanation, find_similar_transactions
        except ImportError as e:
            self.logger.error(f"Required AI utilities not available: {str(e)}")
            return False
        
        try:
            # Test configuration
            base_delay = 2
            test_requests = 3
            results = {feature: {
                'success': 0,
                'rate_limits': 0,
                'errors': [],
                'total_time': 0
            } for feature in ['ASF', 'ESF', 'ERF']}
            
            # Sample test data
            test_data = {
                'description': "Monthly office rent payment",
                'explanation': "Regular monthly payment for office space",
                'accounts': [{'name': 'Rent Expense', 'category': 'Expenses', 'link': '510'}]
            }

            # Define test functions with proper error handling
            features_test = {
                'ASF': lambda: self._safe_execute(
                    lambda: predict_account(
                        test_data['description'],
                        test_data['explanation'],
                        test_data['accounts']
                    ),
                    "Account Suggestion Feature"
                ),
                'ESF': lambda: self._safe_execute(
                    lambda: suggest_explanation(test_data['description']),
                    "Explanation Suggestion Feature"
                ),
                'ERF': lambda: self._safe_execute(
                    lambda: find_similar_transactions(
                        test_data['description'],
                        [{'description': 'Similar rent payment', 'id': 1}]
                    ),
                    "Explanation Recognition Feature"
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
            
            # Execute all feature tests with proper error handling
            try:
                with ThreadPoolExecutor(max_workers=concurrent_requests) as executor:
                    futures = []
                    for feature_name, test_func in features_test.items():
                        for request_id in range(test_requests):
                            futures.append(
                                executor.submit(
                                    run_feature_test,
                                    feature_name,
                                    test_func,
                                    request_id + 1
                                )
                            )
                    
                    # Wait for all tests to complete
                    all_results = [future.result() for future in as_completed(futures)]
                    all_tests_passed = all(all_results)
                    
                    if all_tests_passed:
                        self.logger.info("All rate limit tests passed successfully")
                        self.verification_results['rate_limits'] = True
                    else:
                        self.logger.error("One or more rate limit tests failed")
                        
                    return all_tests_passed
                    
            except Exception as e:
                self.logger.error(f"Error executing rate limit tests: {str(e)}")
                return False
            
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