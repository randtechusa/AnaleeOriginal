from flask import render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app import app, db
from models import User, Account, Transaction
import pandas as pd
import logging
import os
from sqlalchemy.exc import SQLAlchemyError

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Configure pandas display options for debugging
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('settings'))  # Redirect to Chart of Accounts
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, request.form['password']):
            login_user(user)
            return redirect(url_for('settings'))  # Redirect to Chart of Accounts
        flash('Invalid email or password')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if User.query.count() > 0:
            flash('Registration is closed - single user system')
            return redirect(url_for('login'))

        user = User(
            username=request.form['username'],
            email=request.form['email'],
            password_hash=generate_password_hash(request.form['password'])
        )
        db.session.add(user)
        db.session.commit()
        flash('Registration successful')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename.endswith('.xlsx'):
                try:
                    df = pd.read_excel(file)
                    required_columns = ['Link', 'Account Name', 'Category']
                    if not all(col in df.columns for col in required_columns):
                        flash('Excel file must contain Link, Account Name, and Category columns')
                        return redirect(url_for('settings'))
                    
                    for _, row in df.iterrows():
                        account = Account(
                            link=row['Link'],
                            name=row['Account Name'],
                            category=row['Category'],
                            sub_category=row.get('Sub Category', ''),
                            user_id=current_user.id
                        )
                        db.session.add(account)
                    db.session.commit()
                    flash('Chart of Accounts imported successfully')
                except Exception as e:
                    logger.error(f'Error importing chart of accounts: {str(e)}')
                    flash(f'Error importing chart of accounts: {str(e)}')
                    db.session.rollback()
            else:
                flash('Please upload a valid Excel file (.xlsx)')
        else:
            # Handle manual account addition
            try:
                account = Account(
                    link=request.form['link'],
                    name=request.form['name'],
                    category=request.form['category'],
                    sub_category=request.form.get('sub_category', ''),
                    user_id=current_user.id
                )
                db.session.add(account)
                db.session.commit()
                flash('Account added successfully')
            except Exception as e:
                logger.error(f'Error adding account: {str(e)}')
                flash(f'Error adding account: {str(e)}')
                db.session.rollback()

    accounts = Account.query.filter_by(user_id=current_user.id).all()
    return render_template('settings.html', accounts=accounts)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/account/<int:account_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_account(account_id):
    account = Account.query.get_or_404(account_id)
    if account.user_id != current_user.id:
        flash('Access denied')
        return redirect(url_for('settings'))

    if request.method == 'POST':
        account.link = request.form['link']
        account.name = request.form['name']
        account.category = request.form['category']
        account.sub_category = request.form.get('sub_category', '')
        db.session.commit()
        flash('Account updated successfully')
        return redirect(url_for('settings'))

    return render_template('edit_account.html', account=account)

@app.route('/account/<int:account_id>/delete', methods=['POST'])
@login_required
def delete_account(account_id):
    account = Account.query.get_or_404(account_id)
    if account.user_id != current_user.id:
        flash('Access denied')
        return redirect(url_for('settings'))

    db.session.delete(account)
    db.session.commit()
    flash('Account deleted successfully')
    return redirect(url_for('settings'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Simple dashboard showing account summary
    accounts = Account.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', accounts=accounts)

@app.route('/analyze')
@login_required
def analyze():
    # Get only account links and names for dropdown
    accounts = Account.query.with_entities(Account.link, Account.name).filter_by(user_id=current_user.id).all()
    return render_template('analyze.html', accounts=accounts)