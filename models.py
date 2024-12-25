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
    subscription_status = db.Column(db.String(20), default='pending')  # pending, active, expired, cancelled
    subscription_type = db.Column(db.String(20), default='free')  # free, basic, premium
    subscription_start = db.Column(db.DateTime)
    subscription_end = db.Column(db.DateTime)
    subscription_features = db.Column(db.JSON)  # Store enabled features as JSON

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

class Transaction(db.Model):
    """Model for financial transactions"""
    __tablename__ = 'transaction'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    bank_account_id = db.Column(db.Integer, db.ForeignKey('account.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    explanation = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

class CompanySettings(db.Model):
    """Model for company-specific settings"""
    __tablename__ = 'company_settings'

    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(200), nullable=False)
    financial_year_end = db.Column(db.Integer, nullable=False)
    registration_number = db.Column(db.String(50))
    tax_number = db.Column(db.String(50))
    vat_number = db.Column(db.String(50))
    address = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID."""
    return User.query.get(int(user_id))