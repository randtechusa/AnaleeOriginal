from flask_login import UserMixin
from datetime import datetime
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey
import logging

logger = logging.getLogger(__name__)

# SQLAlchemy instance will be set by init_models
db = None

def init_models(flask_db):
    global db
    db = flask_db
    logger.info("Models initialized with SQLAlchemy instance")
    return db

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(256))
    transactions = relationship('Transaction', backref='user', lazy=True)
    accounts = relationship('Account', backref='user', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'

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
    link = db.Column(db.String(20), unique=True, nullable=False)  # Links from Excel (e.g., ca.810.001)
    category = db.Column(db.String(100), nullable=False)  # Category from Excel (e.g., Balance sheet)
    sub_category = db.Column(db.String(100))  # Sub Category from Excel
    account_code = db.Column(db.String(20))  # Accounts from Excel
    name = db.Column(db.String(100), nullable=False)  # Account Name from Excel (e.g., Ned Bank)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    transactions = db.relationship('Transaction', backref='account', lazy=True)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<Account {self.link}: {self.name}>'
