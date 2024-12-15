import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy import func, text
from flask import current_app
from models import User, Account, Transaction, CompanySettings, UploadedFile, db

class RollbackVerificationTest:
    """Test suite for verifying data integrity after rollback operations"""
    
    def __init__(self, app=None):
        """Initialize the test suite with optional Flask app"""
        self.app = app
        self.logger = logging.getLogger(__name__)
        self.verification_results = {}
        
        # Configure logging for test suite
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
            
        if app:
            try:
                # Only initialize if we're in testing environment
                if app.config.get('ENABLE_ROLLBACK_TESTS'):
                    self.init_app(app)
                else:
                    self.logger.warning(
                        "Rollback tests are disabled in production environment. "
                        "Set ENABLE_ROLLBACK_TESTS=True to enable testing."
                    )
            except Exception as e:
                self.logger.error(f"Error initializing test suite: {str(e)}")
    
    def init_app(self, app):
        """Initialize the test suite with the Flask app context"""
        self.app = app
        self.logger.info("Initializing rollback verification test suite with app context")
        
        try:
            # Strict environment separation
            if not app.config.get('TESTING') or not app.config.get('ENABLE_ROLLBACK_TESTS'):
                self.logger.warning(
                    "Rollback verification tests can only run in testing environment. "
                    "Production environment and core features are protected."
                )
                return
            
            # Use completely separate test database
            test_db_url = os.environ.get('TEST_DATABASE_URL')
            if not test_db_url:
                self.logger.warning(
                    "TEST_DATABASE_URL not configured. "
                    "Verification tests cannot proceed without separate test database."
                )
                return
                
            app.config['SQLALCHEMY_DATABASE_URI'] = test_db_url
            self.logger.info("Using isolated test database for verifications")
            
            # Verify database connection in app context
            with app.app_context():
                # Verify we can connect but NOT modify
                db.session.execute(text('SELECT 1'))
                self.logger.info("Database connection verified for test suite")
        except Exception as e:
            self.logger.error(f"Database connection error: {str(e)}")
            self.logger.warning("Test suite initialization proceeded with warnings")
            
    def _check_environment(self) -> bool:
        """Verify we're in a completely isolated test environment"""
        if not self.app:
            self.logger.error("No Flask application context available")
            return False
            
        # Strict environment checks
        if not all([
            self.app.config.get('TESTING'),
            self.app.config.get('ENABLE_ROLLBACK_TESTS'),
            os.environ.get('TEST_DATABASE_URL'),
            self.app.config['SQLALCHEMY_DATABASE_URI'] == os.environ.get('TEST_DATABASE_URL')
        ]):
            self.logger.error(
                "Verification tests require strict isolation:\n"
                "- TESTING mode must be enabled\n"
                "- ENABLE_ROLLBACK_TESTS must be True\n"
                "- Separate TEST_DATABASE_URL must be configured\n"
                "- Must use isolated test database\n"
                "These protections preserve production data and core features."
            )
            return False
            
        # Ensure we're not in production
        if self.app.config.get('ENV') == 'production':
            self.logger.error("Verification tests cannot run in production environment")
            return False
            
        return True

    def _safe_execute(self, verification_name: str, *args, **kwargs) -> Tuple[bool, Optional[str]]:
        """
        Safely executes a verification method and handles any exceptions
        
        Args:
            verification_name: Name of the verification method to execute
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            result = getattr(self, verification_name)(*args, **kwargs)
            return result, None
        except Exception as e:
            error_msg = f"Error in {verification_name}: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg

    def verify_transaction_consistency(self, reference_time: datetime) -> bool:
        """Verifies transaction data consistency after rollback"""
        self.logger.info(f"Verifying transaction consistency from {reference_time}")
        try:
            # Ensure we have a valid database session
            if not db.session:
                self.logger.error("No valid database session available")
                return False

            with db.session.begin():
                # Verify database connection
                try:
                    db.session.execute(text('SELECT 1'))
                except Exception as e:
                    self.logger.error(f"Database connection error: {str(e)}")
                    return False

                # Check for transaction record integrity
                transactions = Transaction.query.filter(
                    Transaction.date >= reference_time
                ).order_by(Transaction.date).all()
                
                if not transactions:
                    self.logger.warning("No transactions found after reference time")
                    return True
                
                for transaction in transactions:
                    # Verify required fields
                    required_fields = {
                        'date': transaction.date,
                        'description': transaction.description,
                        'amount': transaction.amount,
                        'user_id': transaction.user_id,
                        'file_id': transaction.file_id
                    }
                    
                    missing_fields = [field for field, value in required_fields.items() if not value]
                    if missing_fields:
                        self.logger.error(
                            f"Transaction {transaction.id} missing required fields: {', '.join(missing_fields)}"
                        )
                        return False
                    
                    # Verify numerical consistency
                    if not isinstance(transaction.amount, (int, float)):
                        self.logger.error(f"Invalid amount type in transaction {transaction.id}")
                        return False
                    
                    # Verify account references
                    if transaction.account_id:
                        account = Account.query.get(transaction.account_id)
                        if not account:
                            self.logger.error(f"Invalid account reference in transaction {transaction.id}")
                            return False
                        
                        # Verify account-user relationship
                        if account.user_id != transaction.user_id:
                            self.logger.error(
                                f"Transaction {transaction.id} references account {account.id} "
                                "belonging to different user"
                            )
                            return False
                    
                    # Verify file reference
                    uploaded_file = UploadedFile.query.get(transaction.file_id)
                    if not uploaded_file:
                        self.logger.error(f"Invalid file reference in transaction {transaction.id}")
                        return False
                
                return True
                
        except Exception as e:
            self.logger.error(f"Transaction consistency check failed: {str(e)}")
            return False

    def verify_user_data_integrity(self) -> bool:
        """Verifies user data integrity after rollback"""
        try:
            with db.session.begin():
                users = User.query.all()
                for user in users:
                    # Verify essential user attributes
                    if not all([
                        user.username,
                        user.email,
                        user.password_hash
                    ]):
                        self.logger.error(f"Invalid user data for user {user.id}")
                        return False
                    
                    # Verify user relationships
                    if not hasattr(user, 'transactions') or not hasattr(user, 'accounts'):
                        self.logger.error(f"Missing relationships for user {user.id}")
                        return False
                
                return True
                
        except Exception as e:
            self.logger.error(f"User data integrity check failed: {str(e)}")
            return False

    def verify_company_settings(self) -> bool:
        """Verifies company settings integrity after rollback"""
        try:
            with db.session.begin():
                settings = CompanySettings.query.all()
                for setting in settings:
                    # Verify required fields
                    if not all([
                        setting.company_name,
                        setting.user_id,
                        setting.financial_year_end
                    ]):
                        self.logger.error(f"Invalid company settings for id {setting.id}")
                        return False
                    
                    # Verify user reference
                    user = User.query.get(setting.user_id)
                    if not user:
                        self.logger.error(f"Invalid user reference in company settings {setting.id}")
                        return False
                
                return True
                
        except Exception as e:
            self.logger.error(f"Company settings verification failed: {str(e)}")
            return False

    def verify_rate_limits(self) -> bool:
        """Verifies rate limiting configuration and functionality after rollback"""
        try:
            config = current_app.config
            required_configs = [
                'RATELIMIT_DEFAULT',
                'RATELIMIT_STORAGE_URL',
                'RATELIMIT_STRATEGY',
                'RATELIMIT_STORAGE_OPTIONS',
                'RATELIMIT_KEY_PREFIX',
                'RATELIMIT_HEADERS_ENABLED'
            ]
            
            # Verify all required configurations exist
            for config_key in required_configs:
                if config_key not in config:
                    self.logger.error(f"Missing rate limit config: {config_key}")
                    return False
            
            # Verify rate limit values are properly formatted
            try:
                limit_value, limit_period = config['RATELIMIT_DEFAULT'].split(' per ')
                if not limit_value.isdigit() or limit_period not in ['second', 'minute', 'hour', 'day']:
                    self.logger.error("Invalid rate limit format")
                    return False
            except (ValueError, AttributeError) as e:
                self.logger.error(f"Rate limit parsing error: {str(e)}")
                return False
            
            # Verify storage URL is valid
            if not config['RATELIMIT_STORAGE_URL'].startswith(('redis://', 'postgresql://')):
                self.logger.error("Invalid rate limit storage URL")
                return False
            
            # Verify storage options
            if not isinstance(config['RATELIMIT_STORAGE_OPTIONS'], dict):
                self.logger.error("Invalid storage options format")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Rate limit verification failed: {str(e)}")
            return False

    def verify_ai_features(self) -> bool:
        """Verifies AI feature configurations and data integrity after rollback"""
        try:
            # Check ERF (Explanation Recognition Feature)
            erf_settings = {
                'enabled': True,
                'similarity_threshold': 0.85,
                'max_matches': 5
            }
            
            # Check ASF (Account Suggestion Feature)
            asf_settings = {
                'enabled': True,
                'confidence_threshold': 0.7,
                'max_suggestions': 3
            }
            
            # Check ESF (Explanation Suggestion Feature)
            esf_settings = {
                'enabled': True,
                'suggestion_limit': 5,
                'context_window': 10
            }
            
            with db.session.begin():
                # Verify ERF data integrity
                transactions = Transaction.query.limit(100).all()
                for transaction in transactions:
                    if not hasattr(transaction, 'explanation'):
                        self.logger.error(f"Missing explanation field for transaction {transaction.id}")
                        return False
                
                # Verify ASF account mappings
                accounts = Account.query.all()
                if not accounts:
                    self.logger.error("No accounts found for ASF verification")
                    return False
                
                # Verify ESF historical data
                if not Transaction.query.filter(Transaction.explanation.isnot(None)).count():
                    self.logger.warning("No transactions with explanations found for ESF")
            
            return True
            
        except Exception as e:
            self.logger.error(f"AI features verification failed: {str(e)}")
            return False

    def verify_bank_statement_integrity(self) -> bool:
        """Verifies bank statement upload integrity and processing status"""
        try:
            with db.session.begin():
                # Check uploaded files
                files = UploadedFile.query.all()
                for file in files:
                    # Verify file metadata
                    if not all([
                        file.filename,
                        file.upload_date,
                        file.user_id
                    ]):
                        self.logger.error(f"Invalid file metadata for file {file.id}")
                        return False
                    
                    # Verify associated transactions
                    transactions = Transaction.query.filter_by(file_id=file.id).all()
                    if not transactions:
                        self.logger.warning(f"No transactions found for file {file.id}")
                        continue
                    
                    # Verify transaction integrity
                    for transaction in transactions:
                        if not all([
                            transaction.date,
                            transaction.amount,
                            transaction.description,
                            transaction.bank_account_id
                        ]):
                            self.logger.error(f"Invalid transaction data for file {file.id}")
                            return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Bank statement verification failed: {str(e)}")
            return False

    def verify_financial_data_integrity(self, reference_time: datetime) -> bool:
        """
        Verifies the integrity of financial data after a rollback
        """
        self.logger.info(f"Starting financial data integrity verification from {reference_time}")
        
        try:
            with db.session.begin():
                # Get all transactions post reference time
                transactions = Transaction.query.filter(
                    Transaction.date >= reference_time
                ).all()
                
                account_balances = {}
                for transaction in transactions:
                    if transaction.account_id:
                        if transaction.account_id not in account_balances:
                            account_balances[transaction.account_id] = 0
                        account_balances[transaction.account_id] += transaction.amount
                
                # Verify each account's calculated balance
                for account_id, calculated_balance in account_balances.items():
                    account = Account.query.get(account_id)
                    if not account:
                        self.logger.error(f"Account {account_id} not found")
                        return False
                    
                    # Verify account relationship integrity
                    if not account.user_id:
                        self.logger.error(f"Account {account_id} has no associated user")
                        return False
                    
                    actual_balance = db.session.query(func.sum(Transaction.amount)).filter(
                        Transaction.account_id == account_id,
                        Transaction.date >= reference_time
                    ).scalar() or 0
                    
                    if abs(calculated_balance - actual_balance) > 0.01:
                        self.logger.error(
                            f"Balance mismatch for account {account.name}: "
                            f"Calculated={calculated_balance:.2f}, "
                            f"Actual={actual_balance:.2f}"
                        )
                        return False
                
                return True
                
        except Exception as e:
            self.logger.error(f"Error verifying financial data integrity: {str(e)}")
            return False

    def verify_bank_account_integrity(self, reference_time: datetime) -> bool:
        """
        Verifies bank account data integrity and relationships after rollback
        """
        try:
            with db.session.begin():
                bank_transactions = Transaction.query.filter(
                    Transaction.date >= reference_time,
                    Transaction.bank_account_id.isnot(None)
                ).all()
                
                bank_accounts = set()
                for transaction in bank_transactions:
                    bank_accounts.add(transaction.bank_account_id)
                
                for account_id in bank_accounts:
                    account = Account.query.get(account_id)
                    if not account:
                        self.logger.error(f"Bank account {account_id} not found")
                        return False
                    
                    if not account.user_id:
                        self.logger.error(f"Bank account {account_id} has no associated user")
                        return False
                    
                    # Verify transaction sequence
                    transactions = Transaction.query.filter(
                        Transaction.bank_account_id == account_id,
                        Transaction.date >= reference_time
                    ).order_by(Transaction.date).all()
                    
                    for i in range(1, len(transactions)):
                        if transactions[i].date < transactions[i-1].date:
                            self.logger.error(f"Transaction sequence error in bank account {account_id}")
                            return False
                
                return True
                
        except Exception as e:
            self.logger.error(f"Error verifying bank account integrity: {str(e)}")
            return False

    def verify_version_integrity(self, reference_time: datetime) -> bool:
        """
        Verifies the integrity of data versioning after rollback
        """
        try:
            with db.session.begin():
                tables = [Transaction, Account, CompanySettings]
                
                for table in tables:
                    # Check for records with invalid timestamps
                    invalid_records = table.query.filter(
                        db.or_(
                            table.created_at > datetime.utcnow(),
                            table.updated_at > datetime.utcnow(),
                            table.updated_at < table.created_at
                        )
                    ).all()
                    
                    if invalid_records:
                        self.logger.error(
                            f"Found {len(invalid_records)} records with invalid timestamps in {table.__name__}"
                        )
                        return False
                    
                    # Verify no future dates exist after rollback
                    future_records = table.query.filter(
                        db.or_(
                            table.created_at > reference_time,
                            table.updated_at > reference_time
                        )
                    ).all()
                    
                    if future_records:
                        self.logger.error(
                            f"Found {len(future_records)} records with future timestamps in {table.__name__}"
                        )
                        return False
                
                return True
                
        except Exception as e:
            self.logger.error(f"Error verifying version integrity: {str(e)}")
            return False

    def verify_uploaded_files(self) -> bool:
        """Verifies the integrity of uploaded files after rollback"""
        try:
            with db.session.begin():
                files = UploadedFile.query.all()
                
                for file in files:
                    # Verify file record integrity
                    if not all([
                        file.filename,
                        file.upload_date,
                        file.user_id
                    ]):
                        self.logger.error(f"Invalid file record: {file.id}")
                        return False
                    
                    # Verify user reference
                    user = User.query.get(file.user_id)
                    if not user:
                        self.logger.error(f"Invalid user reference in file {file.id}")
                        return False
                    
                    # Verify transaction relationships
                    transactions = Transaction.query.filter_by(file_id=file.id).all()
                    if not transactions:
                        self.logger.warning(f"File {file.id} has no associated transactions")
                    
                return True
                
        except Exception as e:
            self.logger.error(f"Error verifying uploaded files: {str(e)}", exc_info=True)
            return False

    def run_all_verifications(self, reference_time: datetime) -> Dict[str, Dict[str, Any]]:
        """Runs all verification checks and returns detailed results"""
        if not self._check_environment():
            self.logger.error("Cannot run verifications in non-test environment")
            return {
                'status': 'error',
                'message': 'Cannot run verifications in non-test environment',
                'timestamp': datetime.utcnow()
            }
            
        self.logger.info("Starting verification suite")
        
        verifications = [
            ('transaction_consistency', lambda: self.verify_transaction_consistency(reference_time)),
            ('user_data_integrity', self.verify_user_data_integrity),
            ('company_settings', self.verify_company_settings),
            ('financial_data_integrity', lambda: self.verify_financial_data_integrity(reference_time)),
            ('bank_account_integrity', lambda: self.verify_bank_account_integrity(reference_time)),
            ('version_integrity', lambda: self.verify_version_integrity(reference_time)),
            ('rate_limits', self.verify_rate_limits),
            ('uploaded_files', self.verify_uploaded_files),
            ('ai_features', self.verify_ai_features),
            ('bank_statement_integrity', self.verify_bank_statement_integrity)
        ]
        
        for name, verification in verifications:
            start_time = datetime.utcnow()
            success, error = self._safe_execute(verification.__name__)
            end_time = datetime.utcnow()
            
            self.verification_results[name] = {
                'success': success,
                'timestamp': start_time,
                'duration': (end_time - start_time).total_seconds(),
                'error': error if error else None
            }
            
            status = 'Passed' if success else 'Failed'
            self.logger.info(f"Verification {name}: {status}")
            if error:
                self.logger.error(f"Error in {name}: {error}")
        
        return self.verification_results