from app import db, login_manager
from flask_login import UserMixin
from datetime import datetime

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    transactions = db.relationship('Transaction', backref='user', lazy=True)
    accounts = db.relationship('Account', backref='user', lazy=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'))
    ai_category = db.Column(db.String(50))
    ai_confidence = db.Column(db.Float)
    ai_explanation = db.Column(db.String(200))  # Store AI's explanation for the categorization

class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    link = db.Column(db.String(20), unique=True, nullable=False)  # Links from Excel
    category = db.Column(db.String(100), nullable=False)  # Category from Excel
    sub_category = db.Column(db.String(100))  # Sub Category from Excel
    account_code = db.Column(db.String(20))  # Accounts from Excel
    name = db.Column(db.String(100), nullable=False)  # Account Name from Excel
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    transactions = db.relationship('Transaction', backref='account', lazy=True)
    is_active = db.Column(db.Boolean, default=True)
