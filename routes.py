from io import StringIO
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app import app, db, logger
from models import User, Account, Transaction
import pandas as pd
import os
import nltk
from nltk.tokenize import word_tokenize

# Download required NLTK data
def categorize_transaction(description):
    """Simple transaction categorization based on description."""
    # This is a placeholder implementation
    description = description.lower()
    confidence = 0.8
    
    if any(word in description for word in ['salary', 'payroll', 'deposit']):
        return 'Income', confidence, 'Transaction appears to be income-related'
    elif any(word in description for word in ['grocery', 'food', 'restaurant']):
        return 'Food & Dining', confidence, 'Transaction appears to be food-related'
    elif any(word in description for word in ['uber', 'lyft', 'taxi', 'transport']):
        return 'Transportation', confidence, 'Transaction appears to be transportation-related'
    else:
        return 'Uncategorized', 0.5, 'Unable to determine category'

try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

@app.route('/')
@login_required
def index():
    return redirect(url_for('settings'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, request.form['password']):
            login_user(user)
            return redirect(url_for('dashboard'))
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

@app.route('/dashboard')
@login_required
def dashboard():
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date.desc()).limit(10)
    total_income = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        Transaction.amount > 0
    ).with_entities(db.func.sum(Transaction.amount)).scalar() or 0

    total_expenses = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        Transaction.amount < 0
    ).with_entities(db.func.sum(Transaction.amount)).scalar() or 0

    return render_template('dashboard.html',
                         transactions=transactions,
                         total_income=total_income,
                         total_expenses=abs(total_expenses))

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file uploaded')
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash('No file selected')
            return redirect(request.url)

        try:
            # Handle both CSV and Excel files
            if file.filename.endswith('.csv'):
                content = file.stream.read().decode('utf-8')
                df = pd.read_csv(StringIO(content))
            else:
                df = pd.read_excel(file)

            for _, row in df.iterrows():
                description = row['Description']
                amount = float(row['Amount'])
                date = pd.to_datetime(row['Date'])

                category, confidence, explanation = categorize_transaction(description)

                transaction = Transaction(
                    date=date,
                    description=description,
                    amount=amount,
                    user_id=current_user.id,
                    ai_category=category,
                    ai_confidence=confidence,
                    ai_explanation=explanation
                )
                db.session.add(transaction)

            db.session.commit()
            flash('Transactions uploaded successfully')

        except Exception as e:
            flash(f'Error processing file: {str(e)}')

    return render_template('upload.html')

@app.route('/analyze')
@login_required
def analyze():
    transactions = Transaction.query.filter_by(user_id=current_user.id).all()
    categories = {}
    for t in transactions:
        cat = t.ai_category or 'Uncategorized'
        if cat not in categories:
            categories[cat] = 0
        categories[cat] += abs(t.amount)

    return render_template('analyze.html',
                         transactions=transactions,
                         categories=categories)

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
                    logger.info(f'Imported {len(df)} accounts from Excel file')
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
                logger.info(f'Added new account: {account.name}')
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