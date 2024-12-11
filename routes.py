from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import logging
import os
from app import db
from models import User, Account, Transaction

# Create blueprint
main = Blueprint('main', __name__)

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Configure pandas display options for debugging
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)

@main.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.settings'))  # Redirect to Chart of Accounts
    return redirect(url_for('main.login'))

@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, request.form['password']):
            login_user(user)
            return redirect(url_for('main.settings'))  # Redirect to Chart of Accounts
        flash('Invalid email or password')
    return render_template('login.html')

@main.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if User.query.count() > 0:
            flash('Registration is closed - single user system')
            return redirect(url_for('main.login'))

        user = User(
            username=request.form['username'],
            email=request.form['email'],
            password_hash=generate_password_hash(request.form['password'])
        )
        try:
            db.session.add(user)
            db.session.commit()
            flash('Registration successful')
            return redirect(url_for('main.login'))
        except Exception as e:
            logger.error(f'Error during registration: {str(e)}')
            db.session.rollback()
            flash('Registration failed. Please try again.')
    return render_template('register.html')

@main.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename.endswith('.xlsx'):
                try:
                    df = pd.read_excel(file)
                    logger.debug(f"Uploaded file columns: {df.columns.tolist()}")
                    
                    # Define column mappings
                    required_columns = {
                        'Links': 'link',
                        'Category': 'category',
                        'Account Name': 'name',
                        'Sub Category': 'sub_category',
                        'Accounts': 'account_code'
                    }
                    
                    # Validate required columns
                    missing_columns = [col for col in required_columns if col not in df.columns]
                    if missing_columns:
                        flash(f'Missing required columns: {", ".join(missing_columns)}')
                        return redirect(url_for('main.settings'))
                    
                    # Process each row
                    for _, row in df.iterrows():
                        existing_account = Account.query.filter_by(
                            link=row['Links'],
                            user_id=current_user.id
                        ).first()
                        
                        account_data = {
                            'link': row['Links'],
                            'name': row['Account Name'],
                            'category': row['Category'],
                            'sub_category': row.get('Sub Category', ''),
                            'account_code': row.get('Accounts', ''),
                            'user_id': current_user.id
                        }
                        
                        if existing_account:
                            logger.info(f"Updating account: {row['Links']}")
                            for key, value in account_data.items():
                                setattr(existing_account, key, value)
                        else:
                            logger.info(f"Creating account: {row['Links']}")
                            account = Account(**account_data)
                            db.session.add(account)
                    
                    db.session.commit()
                    flash('Chart of Accounts imported successfully')
                    logger.info('Chart of Accounts import completed successfully')
                    
                except Exception as e:
                    logger.error(f'Error importing chart of accounts: {str(e)}')
                    logger.exception("Full stack trace:")
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

@main.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))

@main.route('/account/<int:account_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_account(account_id):
    account = Account.query.get_or_404(account_id)
    if account.user_id != current_user.id:
        flash('Access denied')
        return redirect(url_for('main.settings'))

    if request.method == 'POST':
        account.link = request.form['link']
        account.name = request.form['name']
        account.category = request.form['category']
        account.sub_category = request.form.get('sub_category', '')
        try:
            db.session.commit()
            flash('Account updated successfully')
            return redirect(url_for('main.settings'))
        except Exception as e:
            logger.error(f'Error updating account: {str(e)}')
            flash(f'Error updating account: {str(e)}')
            db.session.rollback()

    return render_template('edit_account.html', account=account)

@main.route('/account/<int:account_id>/delete', methods=['POST'])
@login_required
def delete_account(account_id):
    account = Account.query.get_or_404(account_id)
    if account.user_id != current_user.id:
        flash('Access denied')
        return redirect(url_for('main.settings'))

    try:
        db.session.delete(account)
        db.session.commit()
        flash('Account deleted successfully')
    except Exception as e:
        logger.error(f'Error deleting account: {str(e)}')
        flash(f'Error deleting account: {str(e)}')
        db.session.rollback()
    return redirect(url_for('main.settings'))

@main.route('/dashboard')
@login_required
def dashboard():
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date.desc()).limit(5)
    total_income = sum(t.amount for t in Transaction.query.filter(
        Transaction.user_id == current_user.id,
        Transaction.amount > 0
    ).all())
    total_expenses = abs(sum(t.amount for t in Transaction.query.filter(
        Transaction.user_id == current_user.id,
        Transaction.amount < 0
    ).all()))
    return render_template('dashboard.html',
                         transactions=transactions,
                         total_income=total_income,
                         total_expenses=total_expenses)

@main.route('/analyze')
@login_required
def analyze():
    accounts = Account.query.filter_by(user_id=current_user.id).all()
    return render_template('analyze.html', accounts=accounts)

@main.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file uploaded')
            return redirect(url_for('main.upload'))
            
        file = request.files['file']
        if not file.filename:
            flash('No file selected')
            return redirect(url_for('main.upload'))
            
        if not file.filename.endswith(('.csv', '.xlsx')):
            flash('Invalid file format. Please upload a CSV or Excel file.')
            return redirect(url_for('main.upload'))
            
        try:
            # Read file content
            if file.filename.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)
                
            # Validate required columns
            required_columns = ['Date', 'Description', 'Amount']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                flash(f'Missing required columns: {", ".join(missing_columns)}')
                return redirect(url_for('main.upload'))
                
            # Process each row
            for _, row in df.iterrows():
                try:
                    # Create transaction record
                    transaction = Transaction(
                        date=pd.to_datetime(str(row['Date']), format='%Y%m%d'),
                        description=str(row['Description']),
                        amount=float(row['Amount']),
                        explanation='',  # Initially empty
                        user_id=current_user.id
                    )
                    db.session.add(transaction)
                except Exception as row_error:
                    logger.error(f'Error processing row: {row} - {str(row_error)}')
                    continue
                    
            db.session.commit()
            flash('File uploaded and processed successfully')
            return redirect(url_for('main.analyze'))
            
        except Exception as e:
            logger.error(f'Error processing file: {str(e)}')
            db.session.rollback()
            flash(f'Error processing file: {str(e)}')
            
    return render_template('upload.html')

@main.route('/output')
@login_required
def output():
    transactions = Transaction.query.filter_by(user_id=current_user.id).all()
    trial_balance = {}
    for transaction in transactions:
        if transaction.account:
            account_name = transaction.account.name
            trial_balance[account_name] = trial_balance.get(account_name, 0) + transaction.amount
    return render_template('output.html', trial_balance=trial_balance)