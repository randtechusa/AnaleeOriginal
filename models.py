import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database
db = SQLAlchemy()

# Initialize login manager
from flask_login import LoginManager
login_manager = LoginManager()

logger = logging.getLogger(__name__)

class User(UserMixin, db.Model):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(256))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships with cascade deletes for proper cleanup
    transactions = relationship('Transaction', backref='user', lazy=True, cascade='all, delete-orphan')
    accounts = relationship('Account', backref='user', lazy=True, cascade='all, delete-orphan')
    company_settings = relationship('CompanySettings', backref='user', uselist=False, lazy=True, cascade='all, delete-orphan')
    financial_goals = relationship('FinancialGoal', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        """Set hashed password."""
        if not password:
            raise ValueError('Password cannot be empty')
        try:
            self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
            logger.info(f"Password hash generated successfully for user {self.username}")
        except Exception as e:
            logger.error(f"Error setting password for user {self.username}: {str(e)}")
            raise

    def check_password(self, password):
        """Check if provided password matches hash."""
        if not password:
            logger.warning("Empty password provided for verification")
            return False
        if not self.password_hash:
            logger.warning(f"No password hash found for user {self.username}")
            return False
        try:
            logger.debug(f"Attempting password verification for user {self.username}")
            result = check_password_hash(self.password_hash, password)
            if result:
                logger.info(f"Password verification successful for user {self.username}")
            else:
                logger.warning(f"Password verification failed for user {self.username}")
            return result
        except Exception as e:
            logger.error(f"Error verifying password for user {self.username}: {str(e)}")
            logger.exception("Full password verification error stacktrace:")
            return False

    def get_id(self):
        """Required for Flask-Login."""
        return str(self.id)

    @property
    def is_active(self):
        """Required for Flask-Login."""
        return True

    @property
    def is_authenticated(self):
        """Required for Flask-Login."""
        return True

    @property
    def is_anonymous(self):
        """Required for Flask-Login."""
        return False

    @property
    def password(self):
        """Password getter - prevents direct access."""
        raise AttributeError('Password is not a readable attribute')

    @password.setter
    def password(self, password):
        """Password setter - automatically hashes the password."""
        self.set_password(password)

    @staticmethod
    def create_default_accounts(user_id):
        """Create default Chart of Accounts for a new user."""
        if not user_id:
            logger.error("Cannot create default accounts: Invalid user_id")
            raise ValueError("Invalid user_id")

        # Check if user already has accounts
        existing_accounts = Account.query.filter_by(user_id=user_id).first()
        if existing_accounts:
            logger.info(f"User {user_id} already has accounts set up")
            return

        default_accounts = [
            # Assets (1000-1999)
            {'link': '1000', 'name': 'Assets', 'category': 'Assets', 'sub_category': 'Current Assets', 'account_code': '1000'},
            {'link': '1100', 'name': 'Cash and Cash Equivalents', 'category': 'Assets', 'sub_category': 'Current Assets', 'account_code': '1100'},
            {'link': '1200', 'name': 'Accounts Receivable', 'category': 'Assets', 'sub_category': 'Current Assets', 'account_code': '1200'},
            {'link': '1300', 'name': 'Inventory', 'category': 'Assets', 'sub_category': 'Current Assets', 'account_code': '1300'},
            {'link': '1400', 'name': 'Prepaid Expenses', 'category': 'Assets', 'sub_category': 'Current Assets', 'account_code': '1400'},
            {'link': '1500', 'name': 'Fixed Assets', 'category': 'Assets', 'sub_category': 'Non-Current Assets', 'account_code': '1500'},
            {'link': '1600', 'name': 'Accumulated Depreciation', 'category': 'Assets', 'sub_category': 'Non-Current Assets', 'account_code': '1600'},

            # Liabilities (2000-2999)
            {'link': '2000', 'name': 'Liabilities', 'category': 'Liabilities', 'sub_category': 'Current Liabilities', 'account_code': '2000'},
            {'link': '2100', 'name': 'Accounts Payable', 'category': 'Liabilities', 'sub_category': 'Current Liabilities', 'account_code': '2100'},
            {'link': '2200', 'name': 'Accrued Expenses', 'category': 'Liabilities', 'sub_category': 'Current Liabilities', 'account_code': '2200'},
            {'link': '2300', 'name': 'Income Tax Payable', 'category': 'Liabilities', 'sub_category': 'Current Liabilities', 'account_code': '2300'},
            {'link': '2400', 'name': 'Sales Tax Payable', 'category': 'Liabilities', 'sub_category': 'Current Liabilities', 'account_code': '2400'},
            {'link': '2500', 'name': 'Long-term Debt', 'category': 'Liabilities', 'sub_category': 'Non-Current Liabilities', 'account_code': '2500'},

            # Equity (3000-3999)
            {'link': '3000', 'name': 'Equity', 'category': 'Equity', 'sub_category': 'Owner Equity', 'account_code': '3000'},
            {'link': '3100', 'name': 'Common Stock', 'category': 'Equity', 'sub_category': 'Owner Equity', 'account_code': '3100'},
            {'link': '3200', 'name': 'Retained Earnings', 'category': 'Equity', 'sub_category': 'Owner Equity', 'account_code': '3200'},
            {'link': '3300', 'name': 'Dividends', 'category': 'Equity', 'sub_category': 'Owner Equity', 'account_code': '3300'},

            # Income (4000-4999)
            {'link': '4000', 'name': 'Revenue', 'category': 'Income', 'sub_category': 'Operating Revenue', 'account_code': '4000'},
            {'link': '4100', 'name': 'Sales Revenue', 'category': 'Income', 'sub_category': 'Operating Revenue', 'account_code': '4100'},
            {'link': '4200', 'name': 'Service Revenue', 'category': 'Income', 'sub_category': 'Operating Revenue', 'account_code': '4200'},
            {'link': '4300', 'name': 'Interest Income', 'category': 'Income', 'sub_category': 'Non-Operating Revenue', 'account_code': '4300'},
            {'link': '4400', 'name': 'Other Income', 'category': 'Income', 'sub_category': 'Non-Operating Revenue', 'account_code': '4400'},

            # Expenses (5000-5999)
            {'link': '5000', 'name': 'Expenses', 'category': 'Expenses', 'sub_category': 'Operating Expenses', 'account_code': '5000'},
            {'link': '5100', 'name': 'Cost of Goods Sold', 'category': 'Expenses', 'sub_category': 'Operating Expenses', 'account_code': '5100'},
            {'link': '5200', 'name': 'Salaries and Wages', 'category': 'Expenses', 'sub_category': 'Operating Expenses', 'account_code': '5200'},
            {'link': '5300', 'name': 'Rent Expense', 'category': 'Expenses', 'sub_category': 'Operating Expenses', 'account_code': '5300'},
            {'link': '5400', 'name': 'Utilities Expense', 'category': 'Expenses', 'sub_category': 'Operating Expenses', 'account_code': '5400'},
            {'link': '5500', 'name': 'Insurance Expense', 'category': 'Expenses', 'sub_category': 'Operating Expenses', 'account_code': '5500'},
            {'link': '5600', 'name': 'Depreciation Expense', 'category': 'Expenses', 'sub_category': 'Operating Expenses', 'account_code': '5600'},
            {'link': '5700', 'name': 'Interest Expense', 'category': 'Expenses', 'sub_category': 'Non-Operating Expenses', 'account_code': '5700'},
            {'link': '5800', 'name': 'Other Expenses', 'category': 'Expenses', 'sub_category': 'Non-Operating Expenses', 'account_code': '5800'}
        ]

        try:
            # Start a new transaction
            for account_data in default_accounts:
                try:
                    account = Account(
                        user_id=user_id,
                        link=account_data['link'],
                        name=account_data['name'],
                        category=account_data['category'],
                        sub_category=account_data['sub_category'],
                        is_active=True
                    )
                    db.session.add(account)
                except Exception as account_error:
                    logger.error(f"Error creating account {account_data['name']}: {str(account_error)}")
                    raise

            db.session.commit()
            logger.info(f"Successfully created default Chart of Accounts for user {user_id}")

        except Exception as e:
            logger.error(f"Error creating default accounts for user {user_id}: {str(e)}")
            db.session.rollback()
            raise
    def __repr__(self):
        return f'<User {self.username}>'

class UploadedFile(db.Model):
    __tablename__ = 'uploaded_file'

    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable=False)
    upload_date = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)

    # Relationships
    transactions = relationship('Transaction', backref='file', lazy=True)

class Transaction(db.Model):
    __tablename__ = 'transaction'

    id = Column(Integer, primary_key=True)
    date = Column(DateTime, nullable=False)
    description = Column(String(200), nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String(50))
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    account_id = Column(Integer, ForeignKey('account.id'))
    file_id = Column(Integer, ForeignKey('uploaded_file.id'))
    ai_category = Column(String(50))
    ai_confidence = Column(Float)
    ai_explanation = Column(String(200))
    explanation = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    account = relationship('Account', backref='transactions')
    uploaded_file = relationship('UploadedFile', back_populates='transactions')

    def __repr__(self):
        return f'<Transaction {self.date}: {self.description}>'

class Account(db.Model):
    __tablename__ = 'account'

    id = Column(Integer, primary_key=True)
    link = Column(String(20), nullable=False)
    category = Column(String(100), nullable=False)
    sub_category = Column(String(100))
    account_code = Column(String(20))
    name = Column(String(100), nullable=False)
    user_id = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Account {self.link}: {self.name}>'

class CompanySettings(db.Model):
    __tablename__ = 'company_settings'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    company_name = Column(String(200), nullable=False)
    registration_number = Column(String(50))
    tax_number = Column(String(50))
    vat_number = Column(String(50))
    address = Column(Text)
    financial_year_end = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_financial_year(self, date=None, year=None):
        """Get financial year dates based on provided date or year.
        If neither is provided, uses current date.
        Financial year starts from month after financial_year_end and ends on financial_year_end of next year."""
        if date is None and year is None:
            date = datetime.utcnow()

        if year is not None:
            # If year is provided, use it as the start year
            start_year = year
        else:
            # If date's month is after financial year end, start year is the same as date year
            # Otherwise, start year is the previous year
            if date.month > self.financial_year_end:
                start_year = date.year
            else:
                start_year = date.year - 1

        end_year = start_year + 1

        # Start date is always the first day of the month after financial_year_end
        start_month = self.financial_year_end + 1 if self.financial_year_end < 12 else 1
        start_year_adj = start_year if self.financial_year_end < 12 else start_year + 1
        start_date = datetime(start_year_adj, start_month, 1)

        # End date is the last day of financial_year_end month in the next year
        if self.financial_year_end == 2:
            # Handle February and leap years
            last_day = 29 if end_year % 4 == 0 and (end_year % 100 != 0 or end_year % 400 == 0) else 28
        elif self.financial_year_end in [4, 6, 9, 11]:
            last_day = 30
        else:
            last_day = 31

        end_date = datetime(end_year, self.financial_year_end, last_day)

        return {
            'start_date': start_date,
            'end_date': end_date,
            'start_year': start_year,
            'end_year': end_year
        }

class KeywordRule(db.Model):
    """Model for storing keyword-based categorization rules"""
    __tablename__ = 'keyword_rule'

    id = Column(Integer, primary_key=True)
    keyword = Column(String(200), nullable=False)
    category = Column(String(100), nullable=False)
    priority = Column(Integer, default=1)
    is_regex = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<KeywordRule {self.keyword}: {self.category}>'

class HistoricalData(db.Model):
    """Model for storing historical transaction data used for training"""
    __tablename__ = 'historical_data'

    id = Column(Integer, primary_key=True)
    date = Column(DateTime, nullable=False)
    description = Column(String(200), nullable=False)
    amount = Column(Float, nullable=False)
    explanation = Column(String(200))
    account_id = Column(Integer, ForeignKey('account.id'))
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    upload_date = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    account = relationship('Account', backref='historical_data')
    user = relationship('User', backref='historical_data')

    def __repr__(self):
        return f'<HistoricalData {self.date}: {self.description}>'

class RiskAssessment(db.Model):
    """Model for storing financial risk assessments"""
    __tablename__ = 'risk_assessment'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    assessment_date = Column(DateTime, default=datetime.utcnow)
    risk_score = Column(Float, nullable=False)
    risk_level = Column(String(20), nullable=False)  # low, medium, high
    assessment_type = Column(String(50), nullable=False)  # liquidity, solvency, operational
    findings = Column(Text)
    recommendations = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship('User', backref='risk_assessments')

    def __repr__(self):
        return f'<RiskAssessment {self.assessment_date}: {self.risk_level}>'

class RiskIndicator(db.Model):
    """Model for storing specific risk indicators"""
    __tablename__ = 'risk_indicator'

    id = Column(Integer, primary_key=True)
    assessment_id = Column(Integer, ForeignKey('risk_assessment.id'), nullable=False)
    indicator_name = Column(String(100), nullable=False)
    indicator_value = Column(Float, nullable=False)
    threshold_value = Column(Float, nullable=False)
    is_breach = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    assessment = relationship('RiskAssessment', backref='indicators')

    def __repr__(self):
        return f'<RiskIndicator {self.indicator_name}: {self.indicator_value}>'

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID."""
    try:
        return User.query.get(int(user_id))
    except Exception as e:
        logger.error(f"Error loading user {user_id}: {str(e)}")
        return None

class AlertConfiguration(db.Model):
    """Model for storing user-defined alert configurations"""
    __tablename__ = 'alert_configuration'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    name = Column(String(100), nullable=False)
    alert_type = Column(String(50), nullable=False)  # transaction, balance, pattern
    threshold_type = Column(String(50), nullable=False)  # amount, percentage, count
    threshold_value = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    notification_method = Column(String(50), default='web')  # web, email
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship('User', backref='alert_configurations')

    def __repr__(self):
        return f'<AlertConfiguration {self.name}: {self.alert_type}>'

class AlertHistory(db.Model):
    """Model for storing detected anomalies and alert history"""
    __tablename__ = 'alert_history'

    id = Column(Integer, primary_key=True)
    alert_config_id = Column(Integer, ForeignKey('alert_configuration.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    alert_message = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False)  # low, medium, high
    status = Column(String(20), default='new')  # new, acknowledged, resolved
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    alert_config = relationship('AlertConfiguration', backref='alert_history')
    user = relationship('User', backref='alert_history')

    def __repr__(self):
        return f'<AlertHistory {self.severity}: {self.alert_message[:50]}>'

class FinancialRecommendation(db.Model):
    """Model for storing AI-generated financial recommendations"""
    __tablename__ = 'financial_recommendation'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    category = Column(String(50), nullable=False)  # cashflow, investment, cost_reduction, etc.
    priority = Column(String(20), nullable=False)  # high, medium, low
    recommendation = Column(Text, nullable=False)
    impact_score = Column(Float)  # Estimated financial impact
    status = Column(String(20), default='new')  # new, in_progress, completed, dismissed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    applied_at = Column(DateTime)

    # Relationships
    user = relationship('User', backref='recommendations')

    def __repr__(self):
        return f'<FinancialRecommendation {self.category}: {self.recommendation[:50]}>'

class RecommendationMetrics(db.Model):
    """Model for tracking recommendation effectiveness"""
    __tablename__ = 'recommendation_metrics'

    id = Column(Integer, primary_key=True)
    recommendation_id = Column(Integer, ForeignKey('financial_recommendation.id'), nullable=False)
    metric_name = Column(String(100), nullable=False)
    baseline_value = Column(Float)
    current_value = Column(Float)
    target_value = Column(Float)
    measured_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    recommendation = relationship('FinancialRecommendation', backref='metrics')

    def __repr__(self):
        return f'<RecommendationMetrics {self.metric_name}: {self.current_value}>'

class FinancialGoal(db.Model):
    """Model for tracking financial goals and progress"""
    __tablename__ = 'financial_goal'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    target_amount = Column(Float, nullable=False)
    current_amount = Column(Float, default=0.0)
    start_date = Column(DateTime, default=datetime.utcnow)
    deadline = Column(DateTime)
    category = Column(String(50))  # savings, investment, debt_reduction, etc.
    status = Column(String(20), default='active')  # active, completed, cancelled
    is_recurring = Column(Boolean, default=False)
    recurrence_period = Column(String(20))  # monthly, quarterly, yearly
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def calculate_progress(self):
        """Calculate current progress as percentage"""
        if self.target_amount == 0:
            return 0
        return min(100, (self.current_amount / self.target_amount) * 100)

    def get_status_details(self):
        """Get detailed status information"""
        progress = self.calculate_progress()
        days_remaining = None
        if self.deadline:
            days_remaining = (self.deadline - datetime.utcnow()).days

        return {
            'progress': progress,
            'days_remaining': days_remaining,
            'is_overdue': days_remaining < 0 if days_remaining is not None else False,
            'status': self.status
        }

    def __repr__(self):
        return f'<FinancialGoal {self.name}: {self.current_amount}/{self.target_amount}>'