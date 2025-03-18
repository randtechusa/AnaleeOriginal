"""
Database setup script for iCountant
Creates all necessary tables for the application
"""

import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_db():
    """Create all database tables from scratch in the correct order"""
    # Create a minimal Flask app for database setup
    app = Flask(__name__)
    
    # Configure SQLite database with absolute path
    basedir = os.path.abspath(os.path.dirname(__file__))
    instance_path = os.path.join(basedir, 'instance')
    db_path = os.path.join(instance_path, 'dev.db')
    
    # Create instance directory if it doesn't exist
    os.makedirs(instance_path, exist_ok=True)
    
    # Use absolute path for database file
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize SQLAlchemy
    db = SQLAlchemy(app)
    
    # Define models in the order they need to be created (dependencies first)
    class User(db.Model):
        """User model for authentication and profile management"""
        __tablename__ = 'users'
        id = db.Column(db.Integer, primary_key=True)
        username = db.Column(db.String(80), unique=True, nullable=False)
        email = db.Column(db.String(120), unique=True, nullable=False)
        password_hash = db.Column(db.String(128))
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        is_active = db.Column(db.Boolean, default=True)
        is_admin = db.Column(db.Boolean, default=False)
    
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
    
    class AuditLog(db.Model):
        """Model for storing audit logs"""
        __tablename__ = 'audit_logs'
        id = db.Column(db.Integer, primary_key=True)
        timestamp = db.Column(db.DateTime, default=datetime.utcnow)
        user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
        action = db.Column(db.String(50), nullable=False)
        resource_type = db.Column(db.String(50), nullable=False)
        resource_id = db.Column(db.String(50))
        description = db.Column(db.Text)
        ip_address = db.Column(db.String(50))
        user_agent = db.Column(db.String(200))
        status = db.Column(db.String(20), default='success')
        additional_data = db.Column(db.Text)
    
    class UploadedFile(db.Model):
        """Model for storing uploaded file information"""
        __tablename__ = 'uploaded_files'
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
        filename = db.Column(db.String(255), nullable=False)
        file_path = db.Column(db.String(500))
        file_size = db.Column(db.Integer)
        file_type = db.Column(db.String(100))
        upload_date = db.Column(db.DateTime, default=datetime.utcnow)
        is_processed = db.Column(db.Boolean, default=False)
        processing_status = db.Column(db.String(50), default='pending')
        row_count = db.Column(db.Integer, default=0)
    
    class Account(db.Model):
        """Financial account model for tracking different account types"""
        __tablename__ = 'accounts'
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(100), nullable=False)
        type = db.Column(db.String(50), nullable=False)
        code = db.Column(db.String(20), unique=True, nullable=False)
        description = db.Column(db.String(200))
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        is_active = db.Column(db.Boolean, default=True)
        user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    class Transaction(db.Model):
        """Financial transaction model with AI-enhanced explanation support"""
        __tablename__ = 'transactions'
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
        date = db.Column(db.DateTime, nullable=False)
        amount = db.Column(db.Numeric(10, 2), nullable=False)
        description = db.Column(db.String(200))
        account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)
        processed_date = db.Column(db.DateTime, nullable=True)
        is_processed = db.Column(db.Boolean, default=False)
        file_id = db.Column(db.Integer, db.ForeignKey('uploaded_files.id'), nullable=True)
        explanation = db.Column(db.String(500))
        explanation_confidence = db.Column(db.Float, default=0.0)
        explanation_source = db.Column(db.String(50))
        similar_transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=True)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    class AdminChartOfAccounts(db.Model):
        """Standard chart of accounts managed by admin"""
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(100), nullable=False)
        type = db.Column(db.String(50), nullable=False)
        code = db.Column(db.String(20), unique=True, nullable=False)
        description = db.Column(db.String(200))
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        is_active = db.Column(db.Boolean, default=True)
    
    class SystemAudit(db.Model):
        """Model for storing system self-audit results"""
        __tablename__ = 'system_audits'
        id = db.Column(db.Integer, primary_key=True)
        timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
        audit_type = db.Column(db.String(100), nullable=False)
        status = db.Column(db.String(50), nullable=False)
        summary = db.Column(db.Text, nullable=False)
        details = db.Column(db.Text, nullable=True)
        performed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
        duration = db.Column(db.Float, nullable=True)
        completed_at = db.Column(db.DateTime, nullable=True)
    
    class AuditFinding(db.Model):
        """Model for storing specific findings from system audits"""
        __tablename__ = 'audit_findings'
        id = db.Column(db.Integer, primary_key=True)
        audit_id = db.Column(db.Integer, db.ForeignKey('system_audits.id'), nullable=False)
        category = db.Column(db.String(100), nullable=False)
        severity = db.Column(db.String(50), nullable=False)
        title = db.Column(db.String(200), nullable=False)
        description = db.Column(db.Text, nullable=False)
        recommendation = db.Column(db.Text, nullable=True)
        status = db.Column(db.String(50), nullable=False, default='open')
        resolved_at = db.Column(db.DateTime, nullable=True)
        resolution_notes = db.Column(db.Text, nullable=True)
        details = db.Column(db.Text, nullable=True)
        timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    class ScheduledJob(db.Model):
        """Model for storing scheduled job information"""
        __tablename__ = 'scheduled_jobs'
        id = db.Column(db.Integer, primary_key=True)
        job_id = db.Column(db.String(100), unique=True, nullable=False)
        description = db.Column(db.String(200))
        enabled = db.Column(db.Boolean, default=True)
        last_run = db.Column(db.DateTime)
        last_status = db.Column(db.String(20))
        last_error = db.Column(db.Text)
        success_count = db.Column(db.Integer, default=0)
        error_count = db.Column(db.Integer, default=0)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Create database tables
    with app.app_context():
        try:
            # Drop existing database if it exists
            if os.path.exists(db_path):
                logger.info(f"Removing existing database at {db_path}")
                os.remove(db_path)
            
            logger.info("Creating database tables...")
            db.create_all()
            
            # Create admin user
            admin_user = User(
                username='admin',
                email='admin@example.com',
                is_admin=True
            )
            admin_user.password_hash = 'pbkdf2:sha256:150000$7ClFXdVB$90d4dab54764886b4338e03e087be06088ebe2c32ebfbe0fb5f4c14c97fd1a7f'  # 'admin'
            
            db.session.add(admin_user)
            db.session.commit()
            
            logger.info("Admin user created successfully")
            logger.info("Database setup completed successfully")
            
            return True
        except Exception as e:
            logger.error(f"Error creating database: {str(e)}")
            return False

if __name__ == '__main__':
    create_db()