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

    # Relationships
    accounts = db.relationship('Account', backref='user', lazy=True)
    transactions = db.relationship('Transaction', backref='user', lazy=True)
    company_settings = db.relationship('CompanySettings', backref='user', lazy=True)
    historical_data = db.relationship('HistoricalData', backref='user', lazy=True)

    def set_password(self, password):
        """Set hashed password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check if provided password matches hash."""
        return check_password_hash(self.password_hash, password)

class Account(db.Model):
    """Account model for bank accounts"""
    __tablename__ = 'account'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    link = db.Column(db.String(128), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Relationships
    bank_statement_uploads = db.relationship('BankStatementUpload', backref='account', lazy=True)
    transactions = db.relationship('Transaction', backref='account', lazy=True)
    historical_data = db.relationship('HistoricalData', backref='account', lazy=True)

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
    company_name = db.Column(db.String(128), nullable=False)
    financial_year_end = db.Column(db.Date, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

class Transaction(db.Model):
    """Model for financial transactions"""
    __tablename__ = 'transaction'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    bank_account_id = db.Column(db.Integer, db.ForeignKey('account.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    file_id = db.Column(db.Integer, db.ForeignKey('bank_statement_upload.id'))
    explanation = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

class HistoricalData(db.Model):
    """Model for historical financial data"""
    __tablename__ = 'historical_data'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    explanation = db.Column(db.Text)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID."""
    return User.query.get(int(user_id))