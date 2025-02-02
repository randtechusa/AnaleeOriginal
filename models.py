"""Database models for the application"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    """User authentication and profile model"""
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

class Account(db.Model):
    """Financial account model"""
    __tablename__ = 'accounts'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    description = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    user = db.relationship('User', backref=db.backref('accounts', lazy=True))

class Transaction(db.Model):
    """Financial transaction model with enhanced explanation support"""
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    description = db.Column(db.String(200))
    explanation = db.Column(db.String(500))
    explanation_confidence = db.Column(db.Float, default=0.0)
    explanation_source = db.Column(db.String(50))
    similar_transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('transactions', lazy=True))
    similar_transaction = db.relationship('Transaction', remote_side=[id])

# Settings and Configuration Models
class CompanySettings(db.Model):
    """Company configuration model"""
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(200), nullable=False)
    business_type = db.Column(db.String(100))
    fiscal_year_start = db.Column(db.DateTime)
    currency = db.Column(db.String(3), default='USD')
    tax_id = db.Column(db.String(50))
    contact_email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    logo_path = db.Column(db.String(500))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('company_settings', lazy=True))

class FinancialGoal(db.Model):
    """Model for tracking user financial goals"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    target_amount = db.Column(db.Numeric(10, 2), nullable=False)
    current_amount = db.Column(db.Numeric(10, 2), default=0)
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    target_date = db.Column(db.DateTime, nullable=False)
    category = db.Column(db.String(50))  # savings, investment, debt_repayment, etc.
    status = db.Column(db.String(20), default='active')  # active, completed, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('financial_goals', lazy=True))

class AdminChartOfAccounts(db.Model):
    """Standard chart of accounts managed by admin"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    description = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

class UploadedFile(db.Model):
    """Model for tracking uploaded files"""
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(50), default='pending')  # pending, processed, failed

    user = db.relationship('User', backref=db.backref('uploads', lazy=True))

class HistoricalData(db.Model):
    """Model for historical financial data"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    balance = db.Column(db.Numeric(10, 2), nullable=False)
    transaction_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('historical_data', lazy=True))
    account = db.relationship('Account', backref=db.backref('historical_data', lazy=True))

class BankStatementUpload(db.Model):
    """Model for tracking bank statement uploads and processing"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='pending')  # pending, processing, completed, failed
    processed_date = db.Column(db.DateTime)
    error_message = db.Column(db.Text)
    total_transactions = db.Column(db.Integer, default=0)
    processed_transactions = db.Column(db.Integer, default=0)
    bank_name = db.Column(db.String(100))
    statement_period_start = db.Column(db.DateTime)
    statement_period_end = db.Column(db.DateTime)

    user = db.relationship('User', backref=db.backref('bank_statement_uploads', lazy=True))

class AlertConfiguration(db.Model):
    """Model for managing alert settings and notifications"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    alert_type = db.Column(db.String(50), nullable=False)  # balance, transaction, goal, anomaly
    threshold = db.Column(db.Numeric(10, 2))  # Amount threshold if applicable
    condition = db.Column(db.String(50))  # above, below, equals
    is_active = db.Column(db.Boolean, default=True)
    notification_method = db.Column(db.String(50), default='email')  # email, sms, in_app
    frequency = db.Column(db.String(50), default='immediate')  # immediate, daily, weekly
    last_triggered = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('alert_configurations', lazy=True))

class ErrorLog(db.Model):
    """Error logging model"""
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    error_type = db.Column(db.String(50))
    error_message = db.Column(db.Text)
    stack_trace = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    user = db.relationship('User', backref=db.backref('error_logs', lazy=True))

class AlertHistory(db.Model):
    """Model for tracking alert history"""
    __tablename__ = 'alert_history'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    alert_config_id = db.Column(db.Integer, db.ForeignKey('alert_configuration.id'), nullable=False)
    alert_message = db.Column(db.String(255), nullable=False)
    severity = db.Column(db.String(50), default='info')
    status = db.Column(db.String(50), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)

    user = db.relationship('User', backref=db.backref('alert_history', lazy=True))
    alert_config = db.relationship('AlertConfiguration', backref=db.backref('alert_history', lazy=True))