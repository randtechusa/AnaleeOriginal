import logging
import os
import base64
import pyotp
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Text, DateTime, Enum as SQLEnum
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

class Transaction(db.Model):
    """Model for financial transactions"""
    __tablename__ = 'transaction'

    id = Column(Integer, primary_key=True)
    date = Column(DateTime, nullable=False)
    description = Column(String(200), nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String(50))
    user_id = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    account_id = Column(Integer, ForeignKey('account.id', ondelete='CASCADE'))
    file_id = Column(Integer, ForeignKey('uploaded_file.id', ondelete='SET NULL'))
    ai_category = Column(String(50))
    ai_confidence = Column(Float)
    ai_explanation = Column(String(200))
    explanation = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Define relationships without backrefs to avoid conflicts
    account = relationship('Account')
    file = relationship('UploadedFile')

    def __repr__(self):
        return f'<Transaction {self.date}: {self.description}>'

class Account(db.Model):
    """Model for financial accounts"""
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

    # Define relationships with cascade delete
    transactions = relationship('Transaction', backref='transaction_account', 
                              cascade='all, delete-orphan',
                              foreign_keys=[Transaction.account_id])

    bank_statement_uploads = relationship('BankStatementUpload',
                                        cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Account {self.link}: {self.name}>'

class BankStatementUpload(db.Model):
    """Model for tracking bank statement uploads"""
    __tablename__ = 'bank_statement_upload'

    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable=False)
    upload_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    status = Column(
        SQLEnum('pending', 'processing', 'completed', 'failed', name='bank_statement_status'),
        nullable=False,
        default='pending'
    )
    error_message = Column(Text)
    processing_notes = Column(Text)

    # Foreign keys with cascade delete
    account_id = Column(Integer, ForeignKey('account.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'), nullable=False)

    # Define relationships without duplicate backrefs
    account = relationship('Account', foreign_keys=[account_id])
    user = relationship('User', foreign_keys=[user_id])

    def __repr__(self):
        return f'<BankStatementUpload {self.filename} ({self.status})>'

    @property
    def is_processed(self):
        """Check if upload has been processed"""
        return self.status in ('completed', 'failed')

    def set_error(self, message: str):
        """Set error status with message"""
        self.status = 'failed'
        self.error_message = message

    def set_success(self, notes: Optional[str] = None):
        """Mark upload as successfully processed"""
        self.status = 'completed'
        if notes:
            self.processing_notes = notes

class User(UserMixin, db.Model):
    """User model with enhanced security features"""
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(256))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_admin = Column(Boolean, default=False)
    subscription_status = Column(String(20), default='pending')
    is_deleted = Column(Boolean, default=False)

    mfa_secret = Column(String(32))
    mfa_enabled = Column(Boolean, default=False)
    reset_token = Column(String(100), unique=True)
    reset_token_expires = Column(DateTime)

    # Define relationships with cascade delete
    transactions = relationship('Transaction', backref='user', cascade='all, delete-orphan')
    accounts = relationship('Account', backref='user', cascade='all, delete-orphan')
    company_settings = relationship('CompanySettings', backref='user', uselist=False, 
                                  cascade='all, delete-orphan')
    bank_statement_uploads = relationship('BankStatementUpload', 
                                        cascade='all, delete-orphan')

    def set_password(self, password):
        """Set hashed password"""
        if not password:
            raise ValueError('Password cannot be empty')
        try:
            self.password_hash = generate_password_hash(password)
            logger.info(f"Password hash generated successfully for user {self.username}")
        except Exception as e:
            logger.error(f"Error setting password for user {self.username}: {str(e)}")
            raise

    def check_password(self, password):
        """Check if provided password matches hash"""
        if not password:
            logger.warning("Empty password provided for verification")
            return False
        if not self.password_hash:
            logger.warning(f"No password hash found for user {self.username}")
            return False
        try:
            result = check_password_hash(self.password_hash, password)
            if result:
                logger.info(f"Password verification successful for user {self.username}")
            else:
                logger.warning(f"Password verification failed for user {self.username}")
            return result
        except Exception as e:
            logger.error(f"Error verifying password for user {self.username}: {str(e)}")
            return False

    def soft_delete(self):
        """Soft delete user by marking as deleted"""
        self.is_deleted = True
        self.subscription_status = 'deactivated'
        logger.info(f"User {self.username} marked as deleted")

    @property
    def is_active(self):
        """Check if user is active for Flask-Login"""
        return not self.is_deleted and self.subscription_status != 'deactivated'

    def __repr__(self):
        return f'<User {self.username}>'

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID with enhanced error handling"""
    try:
        if not user_id:
            logger.warning("No user_id provided to load_user")
            return None

        user = User.query.get(int(user_id))
        if not user:
            logger.warning(f"No user found with id {user_id}")
            return None

        return user
    except ValueError as e:
        logger.error(f"Invalid user_id format: {user_id}")
        return None
    except Exception as e:
        logger.error(f"Error loading user {user_id}: {str(e)}")
        return None

class CompanySettings(db.Model):
    __tablename__ = 'company_settings'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    company_name = Column(String(200), nullable=False)
    registration_number = Column(String(50))
    tax_number = Column(String(50))
    vat_number = Column(String(50))
    address = Column(Text)
    financial_year_end = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class UploadedFile(db.Model):
    __tablename__ = 'uploaded_file'

    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable=False)
    upload_date = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'), nullable=False)

    # Define relationship without circular reference
    transactions = relationship('Transaction', foreign_keys=[Transaction.file_id])

class KeywordRule(db.Model):
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
    __tablename__ = 'historical_data'

    id = Column(Integer, primary_key=True)
    date = Column(DateTime, nullable=False)
    description = Column(String(200), nullable=False)
    amount = Column(Float, nullable=False)
    explanation = Column(String(200))
    account_id = Column(Integer, ForeignKey('account.id'))
    user_id = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    upload_date = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    account = relationship('Account')
    user = relationship('User')

    def __repr__(self):
        return f'<HistoricalData {self.date}: {self.description}>'

class RiskAssessment(db.Model):
    __tablename__ = 'risk_assessment'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    assessment_date = Column(DateTime, default=datetime.utcnow)
    risk_score = Column(Float, nullable=False)
    risk_level = Column(String(20), nullable=False)  # low, medium, high
    assessment_type = Column(String(50), nullable=False)  # liquidity, solvency, operational
    findings = Column(Text)
    recommendations = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship('User')

    def __repr__(self):
        return f'<RiskAssessment {self.assessment_date}: {self.risk_level}>'

class RiskIndicator(db.Model):
    __tablename__ = 'risk_indicator'

    id = Column(Integer, primary_key=True)
    assessment_id = Column(Integer, ForeignKey('risk_assessment.id', ondelete='CASCADE'), nullable=False)
    indicator_name = Column(String(100), nullable=False)
    indicator_value = Column(Float, nullable=False)
    threshold_value = Column(Float, nullable=False)
    is_breach = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    assessment = relationship('RiskAssessment')

    def __repr__(self):
        return f'<RiskIndicator {self.indicator_name}: {self.indicator_value}>'

class AlertConfiguration(db.Model):
    __tablename__ = 'alert_configuration'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    name = Column(String(100), nullable=False)
    alert_type = Column(String(50), nullable=False)  # transaction, balance, pattern
    threshold_type = Column(String(50), nullable=False)  # amount, percentage, count
    threshold_value = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    notification_method = Column(String(50), default='web')  # web, email
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship('User')

    def __repr__(self):
        return f'<AlertConfiguration {self.name}: {self.alert_type}>'

class AlertHistory(db.Model):
    __tablename__ = 'alert_history'

    id = Column(Integer, primary_key=True)
    alert_config_id = Column(Integer, ForeignKey('alert_configuration.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    alert_message = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False)  # low, medium, high
    status = Column(String(20), default='new')  # new, acknowledged, resolved
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    alert_config = relationship('AlertConfiguration')
    user = relationship('User')

    def __repr__(self):
        return f'<AlertHistory {self.severity}: {self.alert_message[:50]}>'

class FinancialRecommendation(db.Model):
    __tablename__ = 'financial_recommendation'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    category = Column(String(50), nullable=False)  # cashflow, investment, cost_reduction, etc.
    priority = Column(String(20), nullable=False)  # high, medium, low
    recommendation = Column(Text, nullable=False)
    impact_score = Column(Float)  # Estimated financial impact
    status = Column(String(20), default='new')  # new, in_progress, completed, dismissed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    applied_at = Column(DateTime)

    user = relationship('User')

    def __repr__(self):
        return f'<FinancialRecommendation {self.category}: {self.recommendation[:50]}>'

class RecommendationMetrics(db.Model):
    __tablename__ = 'recommendation_metrics'

    id = Column(Integer, primary_key=True)
    recommendation_id = Column(Integer, ForeignKey('financial_recommendation.id', ondelete='CASCADE'), nullable=False)
    metric_name = Column(String(100), nullable=False)
    baseline_value = Column(Float)
    current_value = Column(Float)
    target_value = Column(Float)
    measured_at = Column(DateTime, default=datetime.utcnow)

    recommendation = relationship('FinancialRecommendation')

    def __repr__(self):
        return f'<RecommendationMetrics {self.metric_name}: {self.current_value}>'

class FinancialGoal(db.Model):
    __tablename__ = 'financial_goal'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
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

class AdminChartOfAccounts(db.Model):
    __tablename__ = 'admin_chart_of_accounts'

    id = Column(Integer, primary_key=True)
    link = Column(String(20), nullable=False, unique=True)  # Maps to 'Links' column
    code = Column(String(20), nullable=False)  # Maps to 'Code' column
    name = Column(String(100), nullable=False)  # Maps to 'Account Name' column
    category = Column(String(50), nullable=False)  # Maps to 'Category' column
    sub_category = Column(String(50))  # Maps to 'Sub Category' column
    description = Column(Text)  # Additional field for account details
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<AdminChartOfAccounts {self.code}: {self.name}>'

    @property
    def serialize(self):
        """Return object data in easily serializable format"""
        return {
            'id': self.id,
            'link': self.link,
            'code': self.code,
            'name': self.name,
            'category': self.category,
            'sub_category': self.sub_category,
            'description': self.description
        }