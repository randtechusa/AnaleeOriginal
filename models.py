"""Database models for the application with enhanced documentation"""
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db

class User(UserMixin, db.Model):
    """User model for authentication and profile management"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    def set_password(self, password):
        """Hash and set user password"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify user password"""
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return str(self.id)

class Account(db.Model):
    """Financial account model for tracking different account types"""
    __tablename__ = 'accounts'

    # Core fields
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    description = db.Column(db.String(200))

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Relationships
    user = db.relationship('User', backref=db.backref('accounts', lazy=True))

class Transaction(db.Model):
    """Financial transaction model with AI-enhanced explanation support"""
    __tablename__ = 'transactions'

    # Core fields
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    description = db.Column(db.String(200))

    # AI-enhanced fields
    explanation = db.Column(db.String(500))
    explanation_confidence = db.Column(db.Float, default=0.0)
    explanation_source = db.Column(db.String(50))
    similar_transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'))

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref=db.backref('transactions', lazy=True))
    similar_transaction = db.relationship('Transaction', remote_side=[id])

class RiskAssessment(db.Model):
    """Model for storing risk assessment results"""
    __tablename__ = 'risk_assessments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    risk_score = db.Column(db.Float, nullable=False)
    risk_level = db.Column(db.String(20), nullable=False)  # low, medium, high
    findings = db.Column(db.Text)
    recommendations = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('risk_assessments', lazy=True))
    indicators = db.relationship('RiskIndicator', backref='assessment', lazy=True)

class RiskIndicator(db.Model):
    """Model for storing individual risk indicators"""
    __tablename__ = 'risk_indicators'
    id = db.Column(db.Integer, primary_key=True)
    assessment_id = db.Column(db.Integer, db.ForeignKey('risk_assessments.id'), nullable=False)
    name = db.Column(db.String(50), nullable=False)  # liquidity_ratio, debt_ratio, etc.
    value = db.Column(db.Float, nullable=False)
    threshold = db.Column(db.Float, nullable=False)
    is_breach = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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

class FinancialRecommendation(db.Model):
    """Model for storing AI-generated financial recommendations"""
    __tablename__ = 'financial_recommendations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    category = db.Column(db.String(50), nullable=False)  # cashflow, cost_reduction, revenue, etc.
    priority = db.Column(db.String(20), nullable=False)  # high, medium, low
    recommendation = db.Column(db.Text, nullable=False)
    impact_score = db.Column(db.Float)
    status = db.Column(db.String(20), default='pending')  # pending, implemented, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    implemented_at = db.Column(db.DateTime)

    user = db.relationship('User', backref=db.backref('recommendations', lazy=True))

class RecommendationMetrics(db.Model):
    """Model for tracking recommendation performance metrics"""
    __tablename__ = 'recommendation_metrics'
    id = db.Column(db.Integer, primary_key=True)
    recommendation_id = db.Column(db.Integer, db.ForeignKey('financial_recommendations.id'), nullable=False)
    metric_name = db.Column(db.String(50), nullable=False)  # accuracy, relevance, implementation_success
    metric_value = db.Column(db.Float, nullable=False)
    measurement_date = db.Column(db.DateTime, default=datetime.utcnow)

    recommendation = db.relationship('FinancialRecommendation', 
                                   backref=db.backref('metrics', lazy=True))

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