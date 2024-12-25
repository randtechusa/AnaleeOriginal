"""Database models with authentication support"""
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager
from datetime import datetime

# Initialize database
db = SQLAlchemy()

# Initialize login manager
login_manager = LoginManager()

class User(UserMixin, db.Model):
    """User model with basic authentication"""
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    is_admin = db.Column(db.Boolean, default=False)

    # Subscription fields
    subscription_status = db.Column(db.String(20), default='pending')  # pending, active, deactivated
    subscription_type = db.Column(db.String(20), default='free')  # free, basic, premium
    subscription_start = db.Column(db.DateTime)
    subscription_end = db.Column(db.DateTime)
    subscription_features = db.Column(db.JSON)  # Store enabled features as JSON

    # Relationships
    accounts = db.relationship('Account', backref='user', lazy=True)
    transactions = db.relationship('Transaction', backref='user', lazy=True)
    company_settings = db.relationship('CompanySettings', backref='user', lazy=True)
    historical_data = db.relationship('HistoricalData', backref='user', lazy=True)
    risk_assessments = db.relationship('RiskAssessment', backref='user', lazy=True)
    bank_statement_uploads = db.relationship('BankStatementUpload', backref='user', lazy=True)
    uploaded_files = db.relationship('UploadedFile', backref='user', lazy=True)
    subscription_history = db.relationship('SubscriptionHistory', backref='user', lazy=True)

    def set_password(self, password):
        """Set hashed password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check if provided password matches hash."""
        return check_password_hash(self.password_hash, password)

    def has_feature_access(self, feature_name):
        """Check if user has access to a specific feature"""
        if self.is_admin:
            return True
        if not self.subscription_features:
            return False
        return feature_name in self.subscription_features.get('enabled_features', [])

    def is_subscription_active(self):
        """Check if user has an active subscription"""
        if self.is_admin:
            return True
        return (self.subscription_status == 'active' and 
                self.subscription_end and 
                self.subscription_end > datetime.utcnow())

class SubscriptionHistory(db.Model):
    """Model for tracking subscription changes"""
    __tablename__ = 'subscription_history'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    change_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    old_status = db.Column(db.String(20))
    new_status = db.Column(db.String(20), nullable=False)
    old_type = db.Column(db.String(20))
    new_type = db.Column(db.String(20), nullable=False)
    change_reason = db.Column(db.String(200))
    changed_by_admin = db.Column(db.Boolean, default=False)

class SubscriptionPlan(db.Model):
    """Model for defining subscription plans"""
    __tablename__ = 'subscription_plan'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    duration_days = db.Column(db.Integer, nullable=False)
    features = db.Column(db.JSON, nullable=False)  # List of features included
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Account(db.Model):
    """Account model for bank accounts"""
    __tablename__ = 'account'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    link = db.Column(db.String(20), nullable=False)
    category = db.Column(db.String(50))
    sub_category = db.Column(db.String(50))
    account_code = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    transactions = db.relationship('Transaction', backref='account', lazy=True)
    historical_data = db.relationship('HistoricalData', backref='account', lazy=True)

class UploadedFile(db.Model):
    """Model for tracking uploaded files"""
    __tablename__ = 'uploaded_file'

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(256), nullable=False)
    upload_date = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Relationships
    transactions = db.relationship('Transaction', backref='uploaded_file', lazy=True)

class BankStatementUpload(db.Model):
    """Model for tracking bank statement uploads"""
    __tablename__ = 'bank_statement_upload'

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(256), nullable=False)
    upload_date = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    status = db.Column(db.String(32), nullable=False, default='pending')
    error_message = db.Column(db.Text)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def set_error(self, message):
        """Set error status and message"""
        self.status = 'error'
        self.error_message = message

    def set_success(self, message=None):
        """Set success status and optional message"""
        self.status = 'success'
        self.error_message = message

class CompanySettings(db.Model):
    """Model for company-specific settings"""
    __tablename__ = 'company_settings'

    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(200), nullable=False)
    financial_year_end = db.Column(db.Integer, nullable=False)  # Keep as INTEGER to match existing DB
    registration_number = db.Column(db.String(50))
    tax_number = db.Column(db.String(50))
    vat_number = db.Column(db.String(50))
    address = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Transaction(db.Model):
    """Model for financial transactions"""
    __tablename__ = 'transaction'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    bank_account_id = db.Column(db.Integer, db.ForeignKey('account.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    file_id = db.Column(db.Integer, db.ForeignKey('uploaded_file.id'))
    explanation = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

class HistoricalData(db.Model):
    """Model for historical financial data"""
    __tablename__ = 'historical_data'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    explanation = db.Column(db.String(200))
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class RiskAssessment(db.Model):
    """Model for financial risk assessments"""
    __tablename__ = 'risk_assessment'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    risk_score = db.Column(db.Float, nullable=False)
    risk_level = db.Column(db.String(32), nullable=False)
    assessment_type = db.Column(db.String(64), nullable=False)
    findings = db.Column(db.Text)
    recommendations = db.Column(db.Text)
    assessment_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationship with risk indicators
    indicators = db.relationship('RiskIndicator', backref='assessment', lazy=True)

class RiskIndicator(db.Model):
    """Model for individual risk indicators within an assessment"""
    __tablename__ = 'risk_indicator'

    id = db.Column(db.Integer, primary_key=True)
    assessment_id = db.Column(db.Integer, db.ForeignKey('risk_assessment.id'), nullable=False)
    indicator_name = db.Column(db.String(64), nullable=False)
    indicator_value = db.Column(db.Float, nullable=False)
    threshold_value = db.Column(db.Float, nullable=False)
    is_breach = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID."""
    return User.query.get(int(user_id))