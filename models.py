import logging
from datetime import datetime
from flask_login import UserMixin, LoginManager
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()

logger = logging.getLogger(__name__)

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(256))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships with cascade deletes for proper cleanup
    transactions = relationship('Transaction', backref='user', lazy=True, cascade='all, delete-orphan')
    accounts = relationship('Account', backref='user', lazy=True, cascade='all, delete-orphan')
    company_settings = relationship('CompanySettings', backref='user', uselist=False, lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        """Set hashed password."""
        if not password:
            raise ValueError('Password cannot be empty')
        try:
            self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
            logger.info(f"Password hash generated successfully for user {self.username}")
        except Exception as e:
            logger.error(f"Error setting password for user {self.username}: {str(e)}")
            raise

    def check_password(self, password):
        """Check if provided password matches hash."""
        if not password:
            logger.warning("Empty password provided for verification")
            return False
        if not self.password_hash:
            logger.warning(f"No password hash found for user {self.username}")
            return False
        try:
            logger.debug(f"Attempting password verification for user {self.username}")
            result = check_password_hash(self.password_hash, password)
            if result:
                logger.info(f"Password verification successful for user {self.username}")
            else:
                logger.warning(f"Password verification failed for user {self.username}")
            return result
        except Exception as e:
            logger.error(f"Error verifying password for user {self.username}: {str(e)}")
            logger.exception("Full password verification error stacktrace:")
            return False

    def get_id(self):
        """Required for Flask-Login."""
        return str(self.id)

    @property
    def is_active(self):
        """Required for Flask-Login."""
        return True

    @property
    def is_authenticated(self):
        """Required for Flask-Login."""
        return True

    @property
    def is_anonymous(self):
        """Required for Flask-Login."""
        return False

    @property
    def password(self):
        """Password getter - prevents direct access."""
        raise AttributeError('Password is not a readable attribute')

    @password.setter
    def password(self, password):
        """Password setter - automatically hashes the password."""
        self.set_password(password)

    @staticmethod
    def create_default_accounts(user_id):
        """Create default Chart of Accounts for a new user."""
        try:
            default_accounts = [
                # Assets (1000-1999)
                {'link': '1000', 'name': 'Assets', 'category': 'Assets', 'sub_category': 'Current Assets'},
                {'link': '1100', 'name': 'Bank Accounts', 'category': 'Assets', 'sub_category': 'Current Assets'},
                {'link': '1200', 'name': 'Accounts Receivable', 'category': 'Assets', 'sub_category': 'Current Assets'},
                {'link': '1300', 'name': 'Inventory', 'category': 'Assets', 'sub_category': 'Current Assets'},
                
                # Liabilities (2000-2999)
                {'link': '2000', 'name': 'Liabilities', 'category': 'Liabilities', 'sub_category': 'Current Liabilities'},
                {'link': '2100', 'name': 'Accounts Payable', 'category': 'Liabilities', 'sub_category': 'Current Liabilities'},
                {'link': '2200', 'name': 'Sales Tax Payable', 'category': 'Liabilities', 'sub_category': 'Current Liabilities'},
                
                # Equity (3000-3999)
                {'link': '3000', 'name': 'Equity', 'category': 'Equity', 'sub_category': None},
                {'link': '3100', 'name': 'Common Stock', 'category': 'Equity', 'sub_category': None},
                {'link': '3200', 'name': 'Retained Earnings', 'category': 'Equity', 'sub_category': None},
                
                # Income (4000-4999)
                {'link': '4000', 'name': 'Revenue', 'category': 'Income', 'sub_category': 'Operating Revenue'},
                {'link': '4100', 'name': 'Sales Revenue', 'category': 'Income', 'sub_category': 'Operating Revenue'},
                {'link': '4200', 'name': 'Service Revenue', 'category': 'Income', 'sub_category': 'Operating Revenue'},
                
                # Expenses (5000-5999)
                {'link': '5000', 'name': 'Expenses', 'category': 'Expenses', 'sub_category': 'Operating Expenses'},
                {'link': '5100', 'name': 'Cost of Goods Sold', 'category': 'Expenses', 'sub_category': 'Operating Expenses'},
                {'link': '5200', 'name': 'Salaries Expense', 'category': 'Expenses', 'sub_category': 'Operating Expenses'},
                {'link': '5300', 'name': 'Rent Expense', 'category': 'Expenses', 'sub_category': 'Operating Expenses'},
                {'link': '5400', 'name': 'Utilities Expense', 'category': 'Expenses', 'sub_category': 'Operating Expenses'}
            ]
            
            for account_data in default_accounts:
                account = Account(
                    user_id=user_id,
                    link=account_data['link'],
                    name=account_data['name'],
                    category=account_data['category'],
                    sub_category=account_data['sub_category'],
                    is_active=True
                )
                db.session.add(account)
            
            db.session.commit()
            logger.info(f"Created default Chart of Accounts for user {user_id}")
        except Exception as e:
            logger.error(f"Error creating default accounts for user {user_id}: {str(e)}")
            db.session.rollback()
            raise
    def __repr__(self):
        return f'<User {self.username}>'

class UploadedFile(db.Model):
    __tablename__ = 'uploaded_file'
    
    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable=False)
    upload_date = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    
    # Relationships
    transactions = relationship('Transaction', backref='file', lazy=True)

class Transaction(db.Model):
    __tablename__ = 'transaction'
    
    id = Column(Integer, primary_key=True)
    date = Column(DateTime, nullable=False)
    description = Column(String(200), nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String(50))
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    account_id = Column(Integer, ForeignKey('account.id'))
    file_id = Column(Integer, ForeignKey('uploaded_file.id'))
    ai_category = Column(String(50))
    ai_confidence = Column(Float)
    ai_explanation = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    account = relationship('Account', backref='transactions')
    uploaded_file = relationship('UploadedFile', back_populates='transactions')

class Account(db.Model):
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

    def __repr__(self):
        return f'<Account {self.link}: {self.name}>'

class CompanySettings(db.Model):
    __tablename__ = 'company_settings'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
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
    """Load user by ID."""
    try:
        return User.query.get(int(user_id))
    except Exception as e:
        logger.error(f"Error loading user {user_id}: {str(e)}")
        return None