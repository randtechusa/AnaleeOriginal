"""Database models for the application with enhanced documentation"""
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db
from sqlalchemy.ext.declarative import declarative_base

# Create a base for standalone table creation during migrations
Base = declarative_base()

# Map of the SQLAlchemy models for the Base class
_base_models = {}

def get_base():
    """Returns the SQLAlchemy Base class for direct table creation 
    with properly mapped model definitions"""
    # Define Base models on-demand to match Flask-SQLAlchemy models
    if not _base_models:
        from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, Text, ForeignKey, Numeric
        from sqlalchemy.orm import relationship
        from datetime import datetime
        
        # Define equivalent Base models for each db.Model class
        # Simple example for key tables
        class User(Base):
            __tablename__ = 'users'
            id = Column(Integer, primary_key=True)
            username = Column(String(80), unique=True, nullable=False)
            email = Column(String(120), unique=True, nullable=False)
            password_hash = Column(String(128))
            created_at = Column(DateTime, default=datetime.utcnow)
            is_active = Column(Boolean, default=True)
            is_admin = Column(Boolean, default=False)
        
        class Account(Base):
            __tablename__ = 'accounts'
            id = Column(Integer, primary_key=True)
            name = Column(String(100), nullable=False)
            type = Column(String(50), nullable=False)
            code = Column(String(20), unique=True, nullable=False)
            description = Column(String(200))
            created_at = Column(DateTime, default=datetime.utcnow)
            is_active = Column(Boolean, default=True)
            user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
        
        class Transaction(Base):
            __tablename__ = 'transactions'
            id = Column(Integer, primary_key=True)
            user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
            date = Column(DateTime, nullable=False)
            amount = Column(Numeric(10, 2), nullable=False)
            description = Column(String(200))
            account_id = Column(Integer, ForeignKey('accounts.id'), nullable=True)
            processed_date = Column(DateTime, nullable=True)
            is_processed = Column(Boolean, default=False)
            file_id = Column(Integer, ForeignKey('uploaded_files.id'), nullable=True)
            explanation = Column(String(500))
            explanation_confidence = Column(Float, default=0.0)
            explanation_source = Column(String(50))
            similar_transaction_id = Column(Integer, ForeignKey('transactions.id'))
            created_at = Column(DateTime, default=datetime.utcnow)
            updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
            
        class UploadedFile(Base):
            __tablename__ = 'uploaded_files'
            id = Column(Integer, primary_key=True)
            filename = Column(String(255), nullable=False)
            file_path = Column(String(500), nullable=False)
            upload_date = Column(DateTime, default=datetime.utcnow)
            user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
            status = Column(String(50), default='pending')
            
        class CompanySettings(Base):
            __tablename__ = 'company_settings'
            id = Column(Integer, primary_key=True)
            company_name = Column(String(200), nullable=False)
            business_type = Column(String(100))
            fiscal_year_start = Column(DateTime)
            currency = Column(String(3), default='USD')
            tax_id = Column(String(50))
            contact_email = Column(String(120))
            phone = Column(String(20))
            address = Column(Text)
            logo_path = Column(String(500))
            user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
            created_at = Column(DateTime, default=datetime.utcnow)
            updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
        
        # Store the models in the map
        _base_models['User'] = User
        _base_models['Account'] = Account
        _base_models['Transaction'] = Transaction
        _base_models['UploadedFile'] = UploadedFile
        _base_models['CompanySettings'] = CompanySettings
    
    return Base

class User(UserMixin, db.Model):
    """User model for authentication and profile management"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)  # Added is_admin field

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
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)
    
    # Processing status
    processed_date = db.Column(db.DateTime, nullable=True)
    is_processed = db.Column(db.Boolean, default=False)
    
    # The file this transaction was uploaded from (if applicable)
    file_id = db.Column(db.Integer, db.ForeignKey('uploaded_files.id'), nullable=True)

    # AI-enhanced fields
    explanation = db.Column(db.String(500))
    explanation_confidence = db.Column(db.Float, default=0.0)
    explanation_source = db.Column(db.String(50))
    similar_transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'))

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref=db.backref('transactions', lazy=True))
    account = db.relationship('Account', backref=db.backref('transactions', lazy=True))
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
    # Bug fix: Removed duplicate account_code column definition

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
    """Enhanced error logging model with detailed tracking"""
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    error_type = db.Column(db.String(50))
    error_message = db.Column(db.Text)
    stack_trace = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    endpoint = db.Column(db.String(100))
    request_method = db.Column(db.String(10))
    request_path = db.Column(db.String(255))
    status_code = db.Column(db.Integer)
    resolved = db.Column(db.Boolean, default=False)
    resolution_time = db.Column(db.DateTime)
    resolution_notes = db.Column(db.Text)

    user = db.relationship('User', backref=db.backref('error_logs', lazy=True))

    @classmethod
    def log_error(cls, error_type, message, stack_trace=None, user_id=None, **kwargs):
        """Centralized error logging method"""
        try:
            error_log = cls(
                error_type=error_type,
                error_message=str(message),
                stack_trace=stack_trace,
                user_id=user_id,
                **kwargs
            )
            db.session.add(error_log)
            db.session.commit()
            return True
        except Exception as e:
            print(f"Failed to log error: {e}")
            return False

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

class AuditLog(db.Model):
    """Audit log model for tracking system activities for administrative review"""
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)  # login, logout, create, update, delete, etc.
    resource_type = db.Column(db.String(100), nullable=False)  # user, transaction, account, etc.
    resource_id = db.Column(db.String(100), nullable=True)  # ID of the affected resource
    description = db.Column(db.Text, nullable=True)  # Detailed description of activity
    ip_address = db.Column(db.String(45), nullable=True)  # IPv6 compatibility
    user_agent = db.Column(db.String(255), nullable=True)  # Browser/client info
    status = db.Column(db.String(50), nullable=False, default='success')  # success, failure, warning
    additional_data = db.Column(db.Text, nullable=True)  # JSON string for additional metadata
    
    user = db.relationship('User', backref=db.backref('audit_logs', lazy=True))
    
    def __repr__(self):
        return f'<AuditLog {self.id}: {self.action} on {self.resource_type}>'
    
    @classmethod
    def log_activity(cls, user_id, action, resource_type, resource_id=None, 
                    description=None, ip_address=None, user_agent=None, 
                    status='success', additional_data=None):
        """Helper method to create an audit log entry"""
        log = cls(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            status=status,
            additional_data=additional_data
        )
        db.session.add(log)
        try:
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            print(f"Error creating audit log: {str(e)}")
            return False

class SystemAudit(db.Model):
    """Model for storing system self-audit results"""
    __tablename__ = 'system_audits'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    audit_type = db.Column(db.String(100), nullable=False)  # security, performance, data-integrity
    status = db.Column(db.String(50), nullable=False)  # passed, failed, warning
    summary = db.Column(db.Text, nullable=False)
    details = db.Column(db.Text, nullable=True)  # JSON formatted details
    performed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    duration = db.Column(db.Float, nullable=True)  # Audit duration in seconds
    
    user = db.relationship('User', backref=db.backref('system_audits', lazy=True))
    findings = db.relationship('AuditFinding', backref='audit', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<SystemAudit {self.id}: {self.audit_type} - {self.status}>'

class AuditFinding(db.Model):
    """Model for storing specific findings from system audits"""
    __tablename__ = 'audit_findings'
    id = db.Column(db.Integer, primary_key=True)
    audit_id = db.Column(db.Integer, db.ForeignKey('system_audits.id'), nullable=False)
    category = db.Column(db.String(100), nullable=False)  # database, security, performance, etc.
    severity = db.Column(db.String(50), nullable=False)  # critical, high, medium, low, info
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    recommendation = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), nullable=False, default='open')  # open, resolved, in_progress
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolution_notes = db.Column(db.Text, nullable=True)
    details = db.Column(db.Text, nullable=True)  # JSON formatted additional details
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class ScheduledJob(db.Model):
    """Model for storing scheduled job information"""
    __tablename__ = 'scheduled_jobs'
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(200))
    enabled = db.Column(db.Boolean, default=True)
    last_run = db.Column(db.DateTime)
    last_status = db.Column(db.String(20))  # success, failed
    last_error = db.Column(db.Text)
    success_count = db.Column(db.Integer, default=0)
    error_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<ScheduledJob {self.job_id}>"