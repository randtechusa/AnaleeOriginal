import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, current_app
from flask_login import login_required, current_user, login_user, logout_user
from models import User, Account, Transaction, UploadedFile, CompanySettings
from app import db
import pandas as pd
import time
from ai_utils import (
    find_similar_transactions,
    predict_account,
    suggest_explanation,
    handle_rate_limit
)

logger = logging.getLogger(__name__)
main = Blueprint('main', __name__)

def process_uploaded_file(file, status):
    """Process the uploaded file and return dataframe and total rows."""
    try:
        if file.filename.endswith('.xlsx'):
            df = pd.read_excel(file)
        elif file.filename.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            raise ValueError('Invalid file format')
            
        total_rows = len(df)
        return df, total_rows
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        raise

def init_upload_status(filename):
    """Initialize the upload status dictionary."""
    return {
        'status': 'processing',
        'filename': filename,
        'total_rows': 0,
        'processed_rows': 0,
        'current_chunk': 0,
        'progress': 0,
        'last_update': datetime.utcnow().isoformat(),
        'errors': []
    }

def process_transaction_rows(df, uploaded_file, user):
    """Process transaction rows from dataframe."""
    processed_rows = 0
    error_rows = []
    
    try:
        for index, row in df.iterrows():
            try:
                transaction = Transaction(
                    date=pd.to_datetime(row['Date']).date(),
                    description=str(row['Description']),
                    amount=float(row['Amount']),
                    file_id=uploaded_file.id,
                    user_id=user.id
                )
                db.session.add(transaction)
                processed_rows += 1
            except Exception as e:
                error_rows.append({
                    'row': index + 2,  # +2 for Excel row number (header + 1-based index)
                    'error': str(e)
                })
                
        db.session.commit()
        return processed_rows, error_rows
        
    except Exception as e:
        logger.error(f"Error processing transactions: {str(e)}")
        db.session.rollback()
        raise

@main.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('main.login'))

@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
        
    if request.method == 'POST':
        try:
            email = request.form.get('email')
            password = request.form.get('password')
            
            if not email or not password:
                flash('Please provide both email and password')
                return render_template('login.html')
                
            user = User.query.filter_by(email=email).first()
            
            if user is None:
                flash('Invalid email address')
                return render_template('login.html')
            
            if not hasattr(user, 'check_password'):
                logger.error('User model missing check_password method')
                flash('Authentication error')
                return render_template('login.html')
                
            if not user.check_password(password):
                flash('Invalid password')
                return render_template('login.html')
                
            login_user(user)
            logger.info(f'User {user.email} logged in successfully')
            return redirect(url_for('main.dashboard'))
            
        except Exception as e:
            logger.error(f'Login error: {str(e)}')
            flash('An error occurred during login')
            return render_template('login.html')
            
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
            password=request.form['password']
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
        try:
            account = Account(
                link=request.form['link'],
                name=request.form['name'],
                category=request.form['category'],
                sub_category=request.form.get('sub_category', ''),
                account_code=request.form.get('account_code', ''),
                user_id=current_user.id
            )
            db.session.add(account)
            db.session.commit()
            flash('Account added successfully')
            logger.info(f'New account added: {account.name}')
        except Exception as e:
            logger.error(f'Error adding account: {str(e)}')
            db.session.rollback()
            flash(f'Error adding account: {str(e)}')

    accounts = Account.query.filter_by(user_id=current_user.id).all()
    return render_template('settings.html', accounts=accounts)

@main.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))

@main.route('/company-settings', methods=['GET', 'POST'])
@login_required
def company_settings():
    settings = CompanySettings.query.filter_by(user_id=current_user.id).first()
    
    if request.method == 'POST':
        try:
            if not settings:
                settings = CompanySettings(user_id=current_user.id)
                db.session.add(settings)
            
            settings.company_name = request.form['company_name']
            settings.registration_number = request.form['registration_number']
            settings.tax_number = request.form['tax_number']
            settings.vat_number = request.form['vat_number']
            settings.address = request.form['address']
            settings.financial_year_end = int(request.form['financial_year_end'])
            
            db.session.commit()
            flash('Company settings updated successfully')
            
        except Exception as e:
            logger.error(f'Error updating company settings: {str(e)}')
            flash('Error updating company settings')
            db.session.rollback()
    
    months = [
        (1, 'January'), (2, 'February'), (3, 'March'),
        (4, 'April'), (5, 'May'), (6, 'June'),
        (7, 'July'), (8, 'August'), (9, 'September'),
        (10, 'October'), (11, 'November'), (12, 'December')
    ]
    
    return render_template(
        'company_settings.html',
        settings=settings,
        months=months
    )

@main.route('/analyze/<int:file_id>', methods=['GET', 'POST'])
@login_required
def analyze(file_id):
    logger.info(f"Starting analysis for file_id: {file_id} for user {current_user.id}")
    logger.debug("Loading file and verifying ownership")
    
    try:
        # Load file and verify ownership with detailed logging
        file = UploadedFile.query.filter_by(id=file_id, user_id=current_user.id).first()
        if not file:
            logger.error(f"File {file_id} not found or unauthorized access for user {current_user.id}")
            flash('File not found or unauthorized access')
            return redirect(url_for('main.upload'))
            
        logger.info(f"Successfully found file: {file.filename} for user {current_user.id}")
            
        # Load active accounts
        accounts = Account.query.filter_by(user_id=current_user.id, is_active=True).all()
        
        # Load transactions with enhanced error handling
        try:
            transactions = Transaction.query.filter_by(
                file_id=file_id, 
                user_id=current_user.id
            ).order_by(Transaction.date).all()
            
            if not transactions:
                logger.warning(f"No transactions found for file {file_id} for user {current_user.id}")
                flash('No transactions found in this file')
                return redirect(url_for('main.upload'))
                
            logger.info(f"Successfully loaded {len(transactions)} transactions for analysis")
            
        except Exception as db_error:
            logger.error(f"Database error loading transactions for file {file_id}: {str(db_error)}")
            flash('Error loading transactions from database')
            return redirect(url_for('main.upload'))
            
        # Initialize insights dictionary for AI features
        transaction_insights = {}
            
        # Process POST request if any
        try:
            if request.method == 'POST':
                for transaction in transactions:
                    explanation_key = f'explanation_{transaction.id}'
                    account_key = f'account_{transaction.id}'
                    
                    if explanation_key in request.form:
                        transaction.explanation = request.form[explanation_key]
                    if account_key in request.form and request.form[account_key]:
                        transaction.account_id = int(request.form[account_key])
                        
                db.session.commit()
                flash('Changes saved successfully', 'success')
        except Exception as e:
            logger.error(f"Error saving changes: {str(e)}")
            db.session.rollback()
            flash('Error saving changes', 'error')

        # Import PredictiveEngine at the start of processing
        from predictive_utils import PredictiveEngine
        engine = PredictiveEngine()
                
        # Process each transaction with both AI and pattern-based predictions
        for transaction in transactions:
            try:
                # 1. Core AI Features (ERF) - Find similar transactions
                similar_trans = find_similar_transactions(
                    transaction.description,
                    Transaction.query.filter(
                        Transaction.user_id == current_user.id,
                        Transaction.id != transaction.id
                    ).all()
                )
                    
                # Prepare account data for predictions
                account_data = [{
                    'name': acc.name,
                    'category': acc.category,
                    'link': acc.link
                } for acc in accounts]
                    
                # 2. Core AI Feature (ASF) - Get AI account suggestions
                ai_account_suggestions = predict_account(
                    transaction.description,
                    transaction.explanation or '',
                    account_data
                )
                    
                # 3. Core AI Feature (ESF) - Get AI explanation suggestions
                ai_explanation = suggest_explanation(
                    transaction.description,
                    similar_trans
                )
                    
                # 4. Pattern & Rule-based predictions
                hybrid_suggestions = engine.get_hybrid_suggestions(
                    transaction.description,
                    transaction.amount,
                    current_user.id,
                    accounts
                )
                    
                # Combine all predictions while preserving core AI features
                transaction_insights[transaction.id] = {
                    'similar_transactions': similar_trans,  # ERF results
                    'account_suggestions': ai_account_suggestions,  # ASF results
                    'explanation_suggestion': ai_explanation,  # ESF results
                    'ai_processed': True,
                    'pattern_matches': hybrid_suggestions.get('pattern_matches', []),
                    'rule_matches': hybrid_suggestions.get('rule_matches', [])
                }
                    
            except Exception as e:
                logger.error(f"Error processing transaction {transaction.id}: {str(e)}")
                transaction_insights[transaction.id] = {
                    'similar_transactions': [],
                    'account_suggestions': [],
                    'explanation_suggestion': None,
                    'ai_processed': False,
                    'error': str(e)
                }
        
        return render_template(
            'analyze.html',
            file=file,
            accounts=accounts,
            transactions=transactions,
            bank_account_id=request.form.get('bank_account', type=int) or request.args.get('bank_account', type=int),
            transaction_insights=transaction_insights
        )
        
    except Exception as e:
        logger.error(f"Error in analyze route: {str(e)}")
        flash('Error loading transaction data')
        return redirect(url_for('main.upload'))

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
    company_settings = CompanySettings.query.filter_by(user_id=current_user.id).first()
    if not company_settings:
        flash('Please configure company settings first.')
        return redirect(url_for('main.company_settings'))
    
    selected_year = request.args.get('year', type=int)
    current_date = datetime.utcnow()
    
    if not selected_year:
        if current_date.month > company_settings.financial_year_end:
            selected_year = current_date.year
        else:
            selected_year = current_date.year - 1
    
    fy_dates = company_settings.get_financial_year(current_date)
    start_date = fy_dates['start_date']
    end_date = fy_dates['end_date']
    
    transactions = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        Transaction.date.between(start_date, end_date)
    ).order_by(Transaction.date.desc()).all()
    
    total_income = sum(t.amount for t in transactions if t.amount > 0)
    total_expenses = abs(sum(t.amount for t in transactions if t.amount < 0))
    transaction_count = len(transactions)
    
    monthly_data = {}
    for transaction in transactions:
        month_key = transaction.date.strftime('%Y-%m')
        if month_key not in monthly_data:
            monthly_data[month_key] = {'income': 0, 'expenses': 0}
        if transaction.amount > 0:
            monthly_data[month_key]['income'] += transaction.amount
        else:
            monthly_data[month_key]['expenses'] += abs(transaction.amount)
    
    sorted_months = sorted(monthly_data.keys())
    monthly_labels = [datetime.strptime(m, '%Y-%m').strftime('%b %Y') for m in sorted_months]
    monthly_income = [monthly_data[m]['income'] for m in sorted_months]
    monthly_expenses = [monthly_data[m]['expenses'] for m in sorted_months]
    
    category_data = {}
    for transaction in transactions:
        if transaction.account and transaction.amount < 0:
            category = transaction.account.category or 'Uncategorized'
            category_data[category] = category_data.get(category, 0) + abs(transaction.amount)
    
    sorted_categories = sorted(category_data.items(), key=lambda x: x[1], reverse=True)
    category_labels = [cat[0] for cat in sorted_categories]
    category_amounts = [cat[1] for cat in sorted_categories]
    
    financial_years = set()
    for t in Transaction.query.filter_by(user_id=current_user.id).all():
        if t.date.month > company_settings.financial_year_end:
            financial_years.add(t.date.year)
        else:
            financial_years.add(t.date.year - 1)
    financial_years = sorted(list(financial_years))
    
    recent_transactions = Transaction.query.filter_by(user_id=current_user.id)\
        .order_by(Transaction.date.desc())\
        .limit(5)\
        .all()
    
    return render_template('dashboard.html',
                         transactions=recent_transactions,
                         total_income=total_income,
                         total_expenses=total_expenses,
                         transaction_count=transaction_count,
                         monthly_labels=monthly_labels,
                         monthly_income=monthly_income,
                         monthly_expenses=monthly_expenses,
                         category_labels=category_labels,
                         category_amounts=category_amounts,
                         financial_years=financial_years,
                         current_year=selected_year)

@main.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    try:
        files = UploadedFile.query.filter_by(user_id=current_user.id).order_by(UploadedFile.upload_date.desc()).all()
        bank_accounts = Account.query.filter(
            Account.user_id == current_user.id,
            Account.link.like('ca.810%'),
            Account.is_active == True
        ).order_by(Account.link).all()
        logger.info(f"Retrieved {len(files)} existing files and {len(bank_accounts)} bank accounts for user {current_user.id}")
        
        if request.method == 'POST':
            logger.debug("Processing file upload request")
            if 'file' not in request.files:
                logger.warning("No file found in request")
                flash('No file uploaded')
                return redirect(url_for('main.upload'))
                
            file = request.files['file']
            if not file.filename:
                logger.warning("Empty filename received")
                flash('No file selected')
                return redirect(url_for('main.upload'))
            
            logger.info(f"Processing uploaded file: {file.filename}")
            
            if not file.filename.endswith(('.csv', '.xlsx')):
                logger.warning(f"Invalid file format: {file.filename}")
                flash('Invalid file format. Please upload a CSV or Excel file.')
                return redirect(url_for('main.upload'))
                
            try:
                uploaded_file = UploadedFile(
                    filename=file.filename,
                    user_id=current_user.id
                )
                db.session.add(uploaded_file)
                db.session.commit()
                
                df, total_rows = process_uploaded_file(file, init_upload_status(file.filename))
                processed_rows, error_rows = process_transaction_rows(df, uploaded_file, current_user)
                
                
                if processed_rows > 0:
                    session['upload_status']['processed_rows'] = processed_rows
                    session['upload_status']['failed_rows'] = len(error_rows)
                    session['upload_status']['status'] = 'complete'
                    session['upload_status']['progress_percentage'] = 100
                    session['upload_status']['errors'] = error_rows
                    session.modified = True
                    flash('File uploaded and processed successfully')
                    return redirect(url_for('main.analyze', file_id=uploaded_file.id))
                else:
                    flash('No transactions could be processed from the file.')
                    return redirect(url_for('main.upload'))
                
            except Exception as e:
                logger.error(f"Error processing file: {str(e)}")
                db.session.rollback()
                flash('Error processing file')
                return redirect(url_for('main.upload'))
                
    except Exception as e:
        logger.error(f"Error in upload route: {str(e)}")
        flash('An error occurred during file upload')
        return redirect(url_for('main.upload'))
        
    return render_template('upload.html', files=files, bank_accounts=bank_accounts)


@main.route('/file/<int:file_id>/delete', methods=['POST'])
@login_required
def delete_file(file_id):
    try:
        file = UploadedFile.query.filter_by(id=file_id, user_id=current_user.id).first_or_404()
        Transaction.query.filter_by(file_id=file.id).delete()
        db.session.delete(file)
        db.session.commit()
        flash('File and associated transactions deleted successfully')
        return redirect(url_for('main.upload'))
    except Exception as e:
        logger.error(f'Error deleting file: {str(e)}')
        db.session.rollback()
        flash('Error deleting file')
        return redirect(url_for('main.upload'))

@main.route('/update_explanation', methods=['POST'])
@login_required
def update_explanation():
    try:
        data = request.get_json()
        transaction_id = data.get('transaction_id')
        explanation = data.get('explanation', '').strip()
        description = data.get('description', '').strip()
        
        if not transaction_id or not description:
            return jsonify({'error': 'Missing required fields'}), 400
            
        transaction = Transaction.query.filter_by(
            id=transaction_id, 
            user_id=current_user.id
        ).first()
        
        if not transaction:
            return jsonify({'error': 'Transaction not found'}), 404
            
        transaction.explanation = explanation
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Explanation updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error updating explanation: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main.route('/predict_account', methods=['POST'])
@login_required
def predict_account_route():
    try:
        data = request.get_json()
        description = data.get('description', '').strip()
        explanation = data.get('explanation', '').strip()
        
        if not description:
            return jsonify({'error': 'Description is required'}), 400
            
        available_accounts = Account.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).all()
        
        if not available_accounts:
            return jsonify({'error': 'No active accounts found'}), 400
        
        account_data = [{
            'name': acc.name,
            'category': acc.category,
            'balance': 0  # Initialize with zero balance
        } for acc in available_accounts]
        
        return jsonify({
            'success': True,
            'accounts': account_data
        })
        
    except Exception as e:
        logger.error(f"Error predicting account: {str(e)}")
        return jsonify({'error': str(e)}), 500

@main.route('/financial-insights')
@login_required
def financial_insights():
    """Financial insights view showing detailed analysis"""
    try:
        company_settings = CompanySettings.query.filter_by(user_id=current_user.id).first()
        if not company_settings:
            flash('Please configure company settings first.')
            return redirect(url_for('main.company_settings'))
        
        # Get current financial year dates
        fy_dates = company_settings.get_financial_year()
        start_date = fy_dates['start_date']
        end_date = fy_dates['end_date']
        
        # Get transactions for analysis
        transactions = Transaction.query.filter(
            Transaction.user_id == current_user.id,
            Transaction.date.between(start_date, end_date)
        ).order_by(Transaction.date.desc()).all()
        
        return render_template('financial_insights.html',
                             transactions=transactions,
                             start_date=start_date,
                             end_date=end_date)
                             
    except Exception as e:
        logger.error(f"Error in financial insights: {str(e)}")
        flash('Error generating financial insights')
        return redirect(url_for('main.dashboard'))

@main.route('/expense-forecast')
@login_required
def expense_forecast():
    try:
        company_settings = CompanySettings.query.filter_by(user_id=current_user.id).first()
        if not company_settings:
            flash('Please configure company settings first.')
            return redirect(url_for('main.company_settings'))
        
        fy_dates = company_settings.get_financial_year()
        start_date = fy_dates['start_date']
        end_date = fy_dates['end_date']
        
        transactions = Transaction.query.filter(
            Transaction.user_id == current_user.id,
            Transaction.date.between(start_date, end_date)
        ).order_by(Transaction.date.desc()).all()
        
        transaction_data = [{
            'amount': t.amount,
            'description': t.description,
            'date': t.date.strftime('%Y-%m-%d'),
            'account_name': t.account.name if t.account else 'Uncategorized'
        } for t in transactions]
        
        return render_template('expense_forecast.html', 
                             transactions=transaction_data,
                             start_date=start_date.strftime('%Y-%m-%d'),
                             end_date=end_date.strftime('%Y-%m-%d'))
        
    except Exception as e:
        logger.error(f"Error in expense forecast: {str(e)}")
        flash('Error generating expense forecast')
        return redirect(url_for('main.dashboard'))

# Removed problematic verification endpoint to restore stability

@main.route('/upload-progress')
@login_required
def upload_progress():
    try:
        status = session.get('upload_status', {})
        if not status:
            return jsonify({
                'status': 'no_upload',
                'message': 'No upload in progress'
            })
            
        return jsonify({
            'status': status.get('status', 'unknown'),
            'filename': status.get('filename', ''),
            'total_rows': status.get('total_rows', 0),
            'processed_rows': status.get('processed_rows', 0),
            'current_chunk': status.get('current_chunk', 0),
            'progress': status.get('progress', 0),
            'last_update': status.get('last_update'),
            'errors': status.get('errors', [])
        })
        
    except Exception as e:
        logger.error(f"Error checking upload progress: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Error checking upload progress'
        }), 500

def process_transaction(transaction, description):
    try:
        if not transaction or not transaction.description:
            logger.warning(f"Invalid transaction data: {transaction}")
            return None

        similarity = calculate_similarity(transaction.description, description)
        if similarity >= TEXT_THRESHOLD or similarity >= SEMANTIC_THRESHOLD:
            return {
                'transaction': transaction,
                'similarity': similarity
            }
        return None
    except Exception as e:
        logger.error(f"Error processing transaction: {str(e)}")
        return None

def calculate_similarity(description1, description2):
    #Implementation for similarity calculation would go here. Placeholder for now.
    return 0.5 #Placeholder


TEXT_THRESHOLD = 0.8
SEMANTIC_THRESHOLD = 0.7