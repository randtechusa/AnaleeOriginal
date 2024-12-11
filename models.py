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
    bank_account = db.relationship('Account', foreign_keys=[bank_account_id], backref='bank_transactions')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Account(db.Model):
    __tablename__ = 'account'
    
    id = db.Column(db.Integer, primary_key=True)
    link = db.Column(db.String(20), nullable=False)  # Links from Excel (e.g., ca.810.001)
    category = db.Column(db.String(100), nullable=False)  # Category from Excel (e.g., Balance sheet)
    sub_category = db.Column(db.String(100))  # Sub Category from Excel
    account_code = db.Column(db.String(20))  # Accounts from Excel
    name = db.Column(db.String(100), nullable=False)  # Account Name from Excel (e.g., Ned Bank)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    transactions = db.relationship('Transaction', 
                                      foreign_keys=[Transaction.account_id],
                                      backref='account', 
                                      lazy=True)
    bank_transactions = db.relationship('Transaction',
                                      foreign_keys=[Transaction.bank_account_id],
                                      backref='bank_account',
                                      lazy=True)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<Account {self.link}: {self.name}>'
