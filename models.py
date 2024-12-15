from flask_login import UserMixin
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from app import db, login_manager
import logging

logger = logging.getLogger(__name__)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(256))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    transactions = relationship('Transaction', backref='user', lazy=True)
    accounts = relationship('Account', backref='user', lazy=True)
    company_settings = relationship('CompanySettings', backref='user', uselist=False, lazy=True)

    def set_password(self, password):
        """Set hashed password."""
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check if provided password matches hash."""
        from werkzeug.security import check_password_hash
        if self.password_hash:
            return check_password_hash(self.password_hash, password)
        return False

    def __repr__(self):
        return f'<User {self.username}>'

class UploadedFile(db.Model):
    __tablename__ = 'uploaded_files'
    
    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable=False)
    upload_date = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Relationships
    transactions = relationship('Transaction', backref='file', lazy=True, cascade='all, delete-orphan')

class Transaction(db.Model):
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True)
    date = Column(DateTime, nullable=False)
    description = Column(String(200), nullable=False)
    amount = Column(Float, nullable=False)
    explanation = Column(String(255))
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    account_id = Column(Integer, ForeignKey('account.id'))
    bank_account_id = Column(Integer, ForeignKey('account.id'))
    file_id = Column(Integer, ForeignKey('uploaded_files.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    account = relationship('Account', foreign_keys=[account_id], backref='transactions')
    bank_account = relationship('Account', foreign_keys=[bank_account_id], backref='bank_transactions')

class Account(db.Model):
    __tablename__ = 'account'
    
    id = Column(Integer, primary_key=True)
    link = Column(String(20), nullable=False)
    category = Column(String(100), nullable=False)
    sub_category = Column(String(100))
    account_code = Column(String(20))
    name = Column(String(100), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Account {self.link}: {self.name}>'

class CompanySettings(db.Model):
    __tablename__ = 'company_settings'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    company_name = Column(String(200), nullable=False)
    registration_number = Column(String(50))
    tax_number = Column(String(50))
    vat_number = Column(String(50))
    address = Column(Text)
    financial_year_end = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_financial_year(self, date=None, year=None):
        if date is None:
            date = datetime.utcnow()
        
        if year is not None:
            start_year = year
        else:
            if date.month > self.financial_year_end:
                start_year = date.year
            else:
                start_year = date.year - 1
        
        end_year = start_year + 1
        
        if self.financial_year_end == 12:
            start_date = datetime(start_year + 1, 1, 1)
        else:
            start_date = datetime(start_year, self.financial_year_end + 1, 1)
        
        if self.financial_year_end == 12:
            end_date = datetime(end_year, 12, 31)
        else:
            if self.financial_year_end == 2:
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

    def __repr__(self):
        return f'<CompanySettings {self.company_name}>'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
