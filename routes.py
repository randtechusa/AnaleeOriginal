from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app import app, db
from models import User, Transaction, Account
from nlp_utils import categorize_transaction
import pandas as pd
from io import StringIO

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

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
                    for _, row in df.iterrows():
                        account = Account(
                            account_number=str(row['Account Number']),
                            name=row['Account Name'],
                            type=row['Type'],
                            category=row.get('Category', ''),
                            description=row.get('Description', ''),
                            user_id=current_user.id
                        )
                        db.session.add(account)
                    db.session.commit()
                    flash('Chart of Accounts imported successfully')
                except Exception as e:
                    flash(f'Error importing Chart of Accounts: {str(e)}')
                    
        else:
            # Handle manual account addition
            account = Account(
                account_number=request.form['account_number'],
                name=request.form['account_name'],
                type=request.form['account_type'],
                category=request.form.get('category', ''),
                description=request.form.get('description', ''),
                user_id=current_user.id
            )
            db.session.add(account)
            db.session.commit()
            flash('Account added successfully')
        
    accounts = Account.query.filter_by(user_id=current_user.id).order_by(Account.account_number).all()
    return render_template('settings.html', accounts=accounts)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))
