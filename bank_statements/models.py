"""
Models specific to bank statement processing
Keeps bank statement data separate from core modules and historical data
Implements secure isolation pattern
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Enum as SQLEnum
from models import db

class BankStatementUpload(db.Model):
    """
    Model for tracking bank statement uploads
    Completely isolated from historical data processing
    """
    __tablename__ = 'bank_statement_upload'  # Singular form following convention

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(
        SQLEnum('pending', 'processing', 'completed', 'failed', name='bank_statement_status'),
        nullable=False,
        default='pending'
    )
    error_message = db.Column(db.Text)
    processing_notes = db.Column(db.Text)  # For tracking processing details

    # Foreign keys with correct table references
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Relationships
    account = db.relationship('Account', backref=db.backref('bank_statement_uploads', lazy=True))
    user = db.relationship('User', backref=db.backref('bank_statement_uploads', lazy=True))

    def __repr__(self) -> str:
        """String representation of the upload"""
        return f'<BankStatementUpload {self.filename} ({self.status})>'

    @property
    def is_processed(self) -> bool:
        """Check if upload has been processed"""
        return self.status in ('completed', 'failed')

    def set_error(self, message: str) -> None:
        """Set error status with message"""
        self.status = 'failed'
        self.error_message = message

    def set_success(self, notes: Optional[str] = None) -> None:
        """Mark upload as successfully processed"""
        self.status = 'completed'
        if notes:
            self.processing_notes = notes