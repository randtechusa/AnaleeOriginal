from flask_login import UserMixin
from datetime import datetime
from app import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    transactions = db.relationship('Transaction', backref='user', lazy=True)
    accounts = db.relationship('Account', backref='user', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'

class UploadedFile(db.Model):
    __tablename__ = 'uploaded_files'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    transactions = db.relationship('Transaction', backref='file', lazy=True)

class Transaction(db.Model):
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    explanation = db.Column(db.String(255))  # User-provided explanation
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'))
    bank_account_id = db.Column(db.Integer, db.ForeignKey('account.id'))
    file_id = db.Column(db.Integer, db.ForeignKey('uploaded_files.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Define the relationships with explicit foreign keys
    account = db.relationship('Account', 
                            foreign_keys=[account_id],
                            backref=db.backref('transactions', lazy=True))
    bank_account = db.relationship('Account', 
                                 foreign_keys=[bank_account_id],
                                 backref=db.backref('bank_transactions', lazy=True))

class Account(db.Model):
    __tablename__ = 'account'
    
    id = db.Column(db.Integer, primary_key=True)
    link = db.Column(db.String(20), nullable=False)  # Links from Excel (e.g., ca.810.001)
    category = db.Column(db.String(100), nullable=False)  # Category from Excel (e.g., Balance sheet)
    sub_category = db.Column(db.String(100))  # Sub Category from Excel
    account_code = db.Column(db.String(20))  # Accounts from Excel
    name = db.Column(db.String(100), nullable=False)  # Account Name from Excel (e.g., Ned Bank)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<Account {self.link}: {self.name}>'

class CompanySettings(db.Model):
    __tablename__ = 'company_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    company_name = db.Column(db.String(200), nullable=False)
    registration_number = db.Column(db.String(50))
    tax_number = db.Column(db.String(50))
    vat_number = db.Column(db.String(50))
    address = db.Column(db.Text)
    financial_year_end = db.Column(db.Integer, nullable=False)  # Month number (1-12)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('company_settings', lazy=True))

    def get_financial_year(self, date=None, year=None):
        if date is None:
            date = datetime.utcnow()
            
        # If specific year is provided, use it
        if year is not None:
            start_year = year
            end_year = year + 1
        else:
            # Calculate based on current date
            if date.month > self.financial_year_end:
                start_year = date.year
                end_year = date.year + 1
            else:
                start_year = date.year - 1
                end_year = date.year

        # Calculate start date (first day of the month after year end)
        start_month = (self.financial_year_end % 12) + 1
        start_date = datetime(start_year, start_month, 1)
        
        # Calculate end date (last day of financial year end month)
        if self.financial_year_end == 12:
            end_date = datetime(end_year, 12, 31)
        else:
            # Get last day of the month
            if self.financial_year_end == 2:  # February
                last_day = 29 if end_year % 4 == 0 and (end_year % 100 != 0 or end_year % 400 == 0) else 28
            elif self.financial_year_end in [4, 6, 9, 11]:  # 30-day months
                last_day = 30
            else:  # 31-day months
                last_day = 31
                
            end_date = datetime(end_year, self.financial_year_end, last_day)
        
        return {
            'start_date': start_date,
            'end_date': end_date
        }

    def __repr__(self):
        return f'<CompanySettings {self.company_name}>'
