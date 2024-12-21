import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import text
import pandas as pd

from models import (
    db, User, Account, Transaction, UploadedFile, 
    CompanySettings, HistoricalData
)
from ai_insights import FinancialInsightsGenerator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create blueprint
main = Blueprint('main', __name__)

@main.route('/historical-data', methods=['GET', 'POST'])
@login_required
def historical_data():
    """Redirect to the proper historical data blueprint route"""
    return redirect(url_for('historical_data.upload'))

@main.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('main.login'))

@main.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login with enhanced error handling and session management."""
    if current_user.is_authenticated:
        logger.info(f"Already authenticated user {current_user.id} redirected to dashboard")
        return redirect(url_for('main.dashboard'))

    # Clear any existing session data
    session.clear()
    logger.info("Starting login process with cleared session")

    if request.method == 'POST':
        try:
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '')

            if not email or not password:
                logger.warning("Login attempt with missing credentials")
                flash('Please provide both email and password')
                return render_template('login.html')

            # Verify database connection before proceeding
            try:
                db.session.execute(text('SELECT 1'))
            except Exception as db_error:
                logger.error(f"Database connection error: {str(db_error)}")
                db.session.rollback()
                flash('Unable to connect to database. Please try again.')
                return render_template('login.html')

            # Find and verify user
            user = User.query.filter_by(email=email).first()
            if not user:
                logger.warning(f"Login attempt for non-existent user: {email}")
                flash('Invalid email or password')
                return render_template('login.html')

            logger.info(f"Found user {user.username} with ID {user.id}")

            if not user.check_password(password):
                logger.warning(f"Password verification failed for user: {email}")
                flash('Invalid email or password')
                return render_template('login.html')

            # Login successful - set up session
            login_user(user, remember=True)
            logger.info(f"User {email} logged in successfully")

            # Handle redirect
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('main.dashboard')

            logger.info(f"Login successful, redirecting to: {next_page}")
            return redirect(next_page)

        except Exception as e:
            logger.error(f"Error during login process: {str(e)}")
            logger.exception("Full login error stacktrace:")
            db.session.rollback()
            flash('An error occurred during login. Please try again.')
            return render_template('login.html')

    # GET request - show login form
    return render_template('login.html')

@main.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            # Verify database connection first
            try:
                db.session.execute(text('SELECT 1'))
                logger.info("Database connection verified for registration")
            except Exception as db_error:
                logger.error(f"Database connection failed during registration: {str(db_error)}")
                flash('Unable to connect to database. Please try again.')
                return render_template('register.html')

            # Get and validate form data
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '')

            # Validate required fields
            if not username or not email or not password:
                logger.warning("Registration attempt with missing fields")
                flash('All fields are required')
                return render_template('register.html')

            # Validate email format
            from email_validator import validate_email, EmailNotValidError
            try:
                validate_email(email)
            except EmailNotValidError as e:
                logger.warning(f"Invalid email format during registration: {email}")
                flash('Please enter a valid email address')
                return render_template('register.html')

            # Check for existing user
            existing_user = User.query.filter(
                (User.username == username) | (User.email == email)
            ).first()
            if existing_user:
                logger.warning(f"Registration attempt with existing username/email: {username}/{email}")
                flash('Username or email already exists')
                return render_template('register.html')

            # Create new user with enhanced error handling
            try:
                user = User(
                    username=username,
                    email=email
                )
                user.set_password(password)
                logger.info(f"Created new user object for {username}")

                db.session.add(user)
                db.session.commit()
                logger.info(f"Successfully registered new user: {username}")

                # Log the user in after registration
                # Create default Chart of Accounts for the new user
                try:
                    User.create_default_accounts(user.id)
                    logger.info(f"Default Chart of Accounts created for user {user.id}")
                    login_user(user)
                    flash('Registration successful with default Chart of Accounts')
                    return redirect(url_for('main.dashboard'))
                except Exception as e:
                    logger.error(f"Error creating default accounts: {str(e)}")
                    db.session.rollback()
                    flash('Error during registration. Please try again.')
                    return render_template('register.html')

            except Exception as user_error:
                logger.error(f"Error creating user: {str(user_error)}")
                db.session.rollback()
                flash('Error creating user account. Please try again.')
                return render_template('register.html')

        except Exception as e:
            logger.error(f'Unexpected error during registration: {str(e)}')
            logger.exception("Full registration error stacktrace:")
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

@main.route('/analyze')
@login_required
def analyze_list():
    """Show list of files available for analysis"""
    try:
        files = UploadedFile.query.filter_by(user_id=current_user.id).order_by(UploadedFile.upload_date.desc()).all()
        return render_template('analyze_list.html', files=files)
    except Exception as e:
        logger.error(f"Error loading files for analysis: {str(e)}")
        flash('Error loading files', 'error')
        return redirect(url_for('main.dashboard'))

@main.route('/analyze/<int:file_id>')
@login_required
def analyze(file_id):
    """Analyze specific file transactions"""
    logger.info(f"Starting analysis for file_id: {file_id} for user {current_user.id}")

    try:
        # Verify database connection first
        try:
            db.session.execute(text('SELECT 1'))
            logger.info("Database connection verified")
        except Exception as db_error:
            logger.error(f"Database connection error: {str(db_error)}")
            db.session.rollback()
            flash('Unable to connect to database. Please try again.')
            return redirect(url_for('main.upload'))

        # Load file and verify ownership with detailed logging
        file = UploadedFile.query.filter_by(id=file_id, user_id=current_user.id).first()
        logger.info(f"Database query completed. File found: {file is not None}")

        if not file:
            logger.error(f"File {file_id} not found or unauthorized access for user {current_user.id}")
            flash('File not found or unauthorized access')
            return redirect(url_for('main.upload'))

        # Load ALL transactions for the file
        try:
            transactions = Transaction.query.filter_by(
                file_id=file_id,
                user_id=current_user.id
            ).order_by(Transaction.date).all()

            logger.info(f"Found {len(transactions)} total transactions for file {file_id}")

            if not transactions:
                logger.warning(f"No transactions found for file {file_id}")
                flash('No transactions found in this file')
                return redirect(url_for('main.upload'))

            # Load accounts for the user
            accounts = Account.query.filter_by(
                user_id=current_user.id,
                is_active=True
            ).all()

            if not accounts:
                logger.warning(f"No active accounts found for user {current_user.id}")
                flash('Please set up your Chart of Accounts first')
                return redirect(url_for('main.settings'))

            logger.info(f"Successfully loaded {len(accounts)} active accounts")

            # Initialize insights for each transaction
            transaction_insights = {}
            for transaction in transactions:
                logger.info(f"Processing transaction {transaction.id}: {transaction.description}")
                transaction_insights[transaction.id] = {
                    'similar_transactions': [],
                    'pattern_matches': [],
                    'keyword_matches': [],
                    'rule_matches': [],
                    'explanation_suggestion': None,
                    'confidence': 0,
                    'ai_processed': False,
                    'needs_processing': transaction.account_id is None
                }

            # Count unprocessed transactions
            unprocessed_count = sum(1 for t in transactions if t.account_id is None)
            logger.info(f"Found {unprocessed_count} unprocessed transactions")

            if unprocessed_count == 0:
                flash('All transactions have been processed')
            else:
                flash(f'Found {unprocessed_count} transactions that need processing')

            return render_template(
                'analyze.html',
                file=file,
                transactions=transactions,
                accounts=accounts,
                transaction_insights=transaction_insights,
                unprocessed_count=unprocessed_count,
                ai_available=True
            )

        except Exception as tx_error:
            logger.error(f"Error loading transactions: {str(tx_error)}")
            logger.exception("Full transaction loading error:")
            db.session.rollback()
            flash('Error loading transaction data. Please try again.')
            return redirect(url_for('main.upload'))

    except Exception as e:
        logger.error(f"Error in analyze route: {str(e)}")
        logger.exception("Full analyze route error:")
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

    # Get year from request or use earliest transaction year
    earliest_transaction = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date).first()
    latest_transaction = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date.desc()).first()

    # Initialize current_date
    current_date = datetime.utcnow()
    selected_year = request.args.get('year', type=int)

    if not selected_year and earliest_transaction:
        # Default to the year of the earliest transaction
        if earliest_transaction.date.month > company_settings.financial_year_end:
            selected_year = earliest_transaction.date.year
            current_date = earliest_transaction.date
        else:
            selected_year = earliest_transaction.date.year - 1
            current_date = earliest_transaction.date
    elif not selected_year:
        # If no transactions exist, use current year
        if current_date.month > company_settings.financial_year_end:
            selected_year = current_date.year
        else:
            selected_year = current_date.year - 1
    else:
        # If year is selected, create a date object for that year
        current_date = datetime(selected_year, company_settings.financial_year_end, 1)

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
        # Get uploaded files
        files = UploadedFile.query.filter_by(user_id=current_user.id).order_by(UploadedFile.upload_date.desc()).all()
        logger.info(f"Retrieved {len(files)} existing files for user {current_user.id}")

        # Get bank accounts with detailed logging
        try:
            bank_accounts = Account.query.filter(
                Account.user_id == current_user.id,
                Account.link.ilike('ca.810%'),  # Case-insensitive LIKE
                Account.is_active == True
            ).order_by(Account.link).all()

            logger.info(f"Found {len(bank_accounts)} bank accounts for user {current_user.id}")
            if bank_accounts:
                for account in bank_accounts:
                    logger.info(f"Bank account found: ID={account.id}, Link={account.link}, Name={account.name}")
            else:
                logger.warning(f"No bank accounts found for user {current_user.id} with link pattern 'ca.810%'")

            # Query all accounts to verify filter
            all_accounts = Account.query.filter_by(user_id=current_user.id, is_active=True).all()
            logger.info(f"Total active accounts: {len(all_accounts)}")
            logger.info(f"Account links: {[acc.link for acc in all_accounts]}")

        except Exception as e:
            logger.error(f"Error fetching bank accounts: {str(e)}")
            db.session.rollback()
            bank_accounts = []

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

        # Initialize financial insights generator
        insights_generator = FinancialInsightsGenerator()

        # Get AI-generated insights if available
        financial_advice = session.get('financial_advice', {
            'key_insights': [],
            'risk_factors': [],
            'optimization_opportunities': [],
            'strategic_recommendations': [],
            'cash_flow_analysis': {
                'current_status': '',
                'projected_trend': '',
                'key_drivers': [],
                'improvement_suggestions': []
                    }
        })

        return render_template('financial_insights.html',
                             transactions=transactions,
                             start_date=start_date,
                             enddate=end_date,
                             financial_advice=financial_advice)

    except Exception as e:
        logger.error(f"Error in financialinsights: {str(e)}")
        flash('Error generating financial insights')
        return redirect(url_for('main.dashboard'))

@main.route('/generate-insights', methods=['POST'])
@login_required
def generate_insights():
    """Generate AI-powered financial insights"""
    try:
        # Get transactions for the current financial year
        company_settings = CompanySettings.query.filter_by(user_id=current_user.id).first()
        if not company_settings:
            flash('Please configure company settings first.')
            return redirect(url_for('main.company_settings'))

        # Get current financial year dates
        fy_dates = company_settings.get_financial_year()

        # Get transactions for analysis
        transactions = Transaction.query.filter(
            Transaction.user_id == current_user.id,
            Transaction.date.between(fy_dates['start_date'], fy_dates['end_date'])
        ).order_by(Transaction.date.desc()).all()

        # Convert transactions to dictionary format for AI processing
        transaction_data = [{
            'date': t.date.isoformat(),
            'description': t.description,
            'amount': float(t.amount),
            'category': t.account.category if t.account else'Uncategorized'
        } for t in transactions]

        # Generate insights using AI
        insights_generator = FinancialInsightsGenerator()
        insights = insights_generator.generate_transaction_insights(transaction_data)

        if insights.get('success'):
            # Parse AI response and structure it
            financial_advice = {
                'key_insights': _parse_insights(insights['insights']),
                'risk_factors': _extract_risk_factors(insights['insights']),
                'optimization_opportunities': _extract_opportunities(insights['insights']),
                'strategic_recommendations': _extract_recommendations(insights['insights']),
                'cash_flow_analysis': _analyze_cash_flow(transaction_data)
            }
            session['financial_advice'] = financial_advice
            flash('Financial insights generated successfully', 'success')
        else:
            flash('Unable to generate insights at this time', 'error')

        return redirect(url_for('main.financial_insights'))

    except Exception as e:
        logger.error(f"Error generating AI insights: {str(e)}")
        flash('Error generating financial insights')
        return redirect(url_for('main.financial_insights'))

def _parse_insights(insights_text):
    """Parse AI-generated insights into structured format"""
    try:
        # For now, return the raw insights text
        # TODO: Implement more sophisticated parsing
        return insights_text
    except Exception as e:
        logger.error(f"Error parsing insights: {str(e)}")
        return "Unable to parseinsights"

def _extract_risk_factors(insights_text):
    """Extract risk factors fromAI insights"""
    # TODO: Implement risk factorextraction
    return ["Risk analysis will be available in the next update"]

def _extract_opportunities(insights_text):
    """Extract optimization opportunities from AI insights"""
    # TODO: Implement opportunity extraction
    return ["Optimization opportunities will be available in the next update"]

def _extract_recommendations(insights_text):
    """Extract strategic recommendations from AI insights"""
    # TODO: Implement recommendation extraction
    return ["Strategic recommendations will be available in the next update"]

def _analyze_cash_flow(transactions):
    """Analyze cash flow patterns"""
    try:
        total_inflow = sum(t['amount'] for t in transactions if t['amount'] > 0)
        total_outflow = sum(abs(t['amount']) for t in transactions if t['amount'] < 0)
        net_flow = total_inflow - total_outflow

        return {
            'current_status': f"Net cash flow: ${net_flow:,.2f}",
            'projected_trend': "Trend analysis will be available in the next update",
            'key_drivers': [                f"Total inflow: ${total_inflow:,.2f}",
                f"Total outflow: ${total_outflow:,.2f}"
            ],
            'improvement_suggestions': ["Cash flow optimization suggestions will be available in the next update"]
                }
    except Exception as e:
        logger.error(f"Error analyzing cash flow: {str(e)}")
        return {
            'current_status': '',
            'projected_trend': '',
            'key_drivers': [],
            'improvement_suggestions': []
        }

@main.route('/expense-forecast')
@login_required
def expense_forecast():
    """
    Generate and display expense forecasts with proper error handling and data protection
    Returns:
        Template with expense forecast data or redirects to dashboard with error message
    """
    try:
        # Get company settings with validation
        company_settings = CompanySettings.query.filter_by(user_id=current_user.id).first()
        if not company_settings:
            flash('Please configure company settings first.')
            return redirect(url_for('main.company_settings'))

        # Get current financial year dates
        fy_dates = company_settings.get_financial_year()
        start_date = fy_dates['start_date']
        end_date = fy_dates['end_date']

        # Get transactions with proper filtering
        transactions = Transaction.query.filter(
            Transaction.user_id == current_user.id,
            Transaction.date.between(start_date, end_date),
            Transaction.amount < 0  # Only include expenses
        ).order_by(Transaction.date.desc()).all()

        # Initialize forecast structure with all required fields
        forecast = {
            'monthly_forecasts': [],
            'forecast_factors': {
                'key_drivers': [
                    'Historical spending patterns',
                    'Seasonal variations',
                    'Fixed costs'
                ],
                'risk_factors': [
                    'Market volatility',
                    'Unexpected expenses',
                    'Economic conditions'
                ]
            },
            'recommendations': [
                {
                    'action': 'Monitor fixed costs',
                    'implementation_timeline': 'Immediate',
                    'potential_impact': 'Reduce operational expenses'
                },
                {
                    'action': 'Review variable expenses',
                    'implementation_timeline': 'Monthly',
                    'potential_impact': 'Optimize spending patterns'
                }
            ]
        }

        # Process monthly data for forecasting
        monthly_data = {}
        for transaction in transactions:
            month_key = transaction.date.strftime('%Y-%m')
            if month_key not in monthly_data:
                monthly_data[month_key] = {'expenses': 0}
            monthly_data[month_key]['expenses'] += abs(transaction.amount)

        # Generate monthly forecasts
        for month, data in sorted(monthly_data.items()):
            forecast['monthly_forecasts'].append({
                'month': datetime.strptime(month, '%Y-%m').strftime('%B %Y'),
                'total_expenses': data['expenses'],
                'confidence': 0.85,  # Default confidence level
                'breakdown': [
                    {
                        'category': 'Operating Expenses',
                        'amount': data['expenses'],
                        'trend': 'stable'
                    }
                ]
            })

        # Return template with complete forecast data
        return render_template('expense_forecast.html',
                            forecast=forecast,
                            start_date=start_date.strftime('%Y-%m-%d'),
                            end_date=end_date.strftime('%Y-%m-%d'))

    except Exception as e:
        logger.error(f"Error in expense forecast: {str(e)}")
        flash('Error generating expense forecast')
        return redirect(url_for('main.dashboard'))

@main.route('/api/suggest-explanation', methods=['POST'])
@login_required
def suggest_explanation_api():
    """API endpoint for ESF (Explanation Suggestion Feature)"""
    try:
        data = request.get_json()
        description = data.get('description', '').strip()

        if not description:
            return jsonify({'error': 'Description is required'}), 400

        similar_transactions = find_similar_transactions(
            description,
            Transaction.query.filter(
                Transaction.user_id == current_user.id,
                Transaction.explanation.isnot(None)
            ).all()
        )

        suggestion = suggest_explanation(description, similar_transactions)
        return jsonify({
            'success': True,
            'suggestion': suggestion
        })

    except Exception as e:
        logger.error(f"Error in ESF: {str(e)}")
        return jsonify({'error': str(e)}), 500

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

@main.route('/icountant', methods=['GET', 'POST'])
@login_required
def icountant_interface():
    """Handle the iCountant interface with proper transaction processing and AI suggestions"""
    logger.info(f"Starting iCountant interface for user {current_user.id}")

    try:
        # Get total transaction count
        total_count = Transaction.query.filter_by(user_id=current_user.id).count()
        logger.info(f"Total transactions for user {current_user.id}: {total_count}")

        # Get unprocessed transactions
        transactions = Transaction.query.filter_by(
            user_id=current_user.id,
            account_id=None
        ).order_by(Transaction.date).all()

        # Get active accounts for processing
        accounts = Account.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).order_by(Account.category, Account.name).all()
        logger.info(f"Found {len(accounts)} active accounts for user {current_user.id}")

        if request.method == 'POST':
            transaction_id = request.form.get('transaction_id', type=int)
            selected_account = request.form.get('selected_account', type=int)

            if transaction_id and selected_account is not None:
                transaction = Transaction.query.get(transaction_id)
                if transaction and transaction.user_id == current_user.id:
                    if 0 <= selected_account < len(accounts):
                        # Store the AI suggestion before updating
                        if transaction.ai_category:
                            transaction.account_id = accounts[selected_account].id
                            transaction.ai_confidence = float(transaction.ai_confidence or 0.0)
                            db.session.commit()
                            flash('Transaction processed successfully')
                            return redirect(url_for('main.icountant_interface'))

        # Get current transaction and process it
        current_transaction = next((t for t in transactions), None)
        if current_transaction:
            logger.info(f"Processing transaction {current_transaction.id}: {current_transaction.description}")

            # Initialize insights generator
            insights_generator = FinancialInsightsGenerator()

            # Generate insights with AI categorization
            insights = insights_generator.generate_transaction_insights([{
                'date': current_transaction.date.isoformat(),
                'description': current_transaction.description,
                'amount': float(current_transaction.amount),
                'category': current_transaction.account.category if current_transaction.account else None
            }])

            # Store AI suggestions in the transaction
            current_transaction.ai_category = insights['category_suggestion']['category']
            current_transaction.ai_confidence = insights['category_suggestion']['confidence']
            current_transaction.ai_explanation = insights['category_suggestion']['explanation']
            db.session.commit()

            # Format suggestions for display
            suggested_accounts = []
            if insights['category_suggestion']['category']:
                matching_accounts = [acc for acc in accounts 
                                  if acc.category.lower() == insights['category_suggestion']['category'].lower()]
                suggested_accounts = [{
                    'account': acc,
                    'confidence': insights['category_suggestion']['confidence'],
                    'reason': insights['category_suggestion']['explanation']
                } for acc in matching_accounts[:3]]  # Top 3 matching accounts

            transaction_info = {
                'insights': {
                    'amount_formatted': f"${abs(current_transaction.amount):,.2f}",
                    'transaction_type': 'credit' if current_transaction.amount < 0 else 'debit',
                    'ai_insights': insights['insights'],
                    'suggested_accounts': suggested_accounts or [{
                        'account': account,
                        'reason': 'Alternative suggestion based on category'
                    } for account in accounts[:3]]  # Fallback to first 3 accounts if no AI matches
                }
            }
            message = None
        else:
            current_transaction = None
            transaction_info = None
            message = "No transactions pending for processing"

        # Get recently processed transactions
        recently_processed = Transaction.query.filter(
            Transaction.user_id == current_user.id,
            Transaction.account_id.isnot(None)
        ).order_by(Transaction.date.desc()).limit(5).all()

        processed_count = Transaction.query.filter(
            Transaction.user_id == current_user.id,
            Transaction.account_id.isnot(None)
        ).count()

        return render_template(
            'icountant.html',
            transaction=current_transaction,
            transaction_info=transaction_info,
            accounts=accounts,
            message=message,
            recently_processed=recently_processed,
            processed_count=processed_count,
            total_count=total_count
        )

    except Exception as e:
        logger.error(f"Error in iCountant interface: {str(e)}")
        db.session.rollback()
        flash('Error processing transaction')
        return redirect(url_for('main.dashboard'))

class ICountant:
    def __init__(self, accounts):
        self.accounts = accounts

    def process_transaction(self, transaction_data):
        # Placeholder for actual iCountant logic
        message = "iCountant is processing this transaction. Please select an account."
        transaction_info = {}
        return message, transaction_info

    def complete_transaction(self, selected_account_index):
        # Placeholder for actual iCountant logic
        if 0 <= selected_account_index < len(self.accounts):
            message = "Transaction completed successfully!"
            success = True
            completed = True
        else:
            message = "Invalid account selection."
            success = False
            completed = False
        return success, message, completed

# Keep all other existing routes and functions, but remove the duplicate historical_data route at the bottom


def suggest_explanation(description, similar_transactions):
    #Implementation for suggestion would go here. Placeholder for now.
    return "Explanation suggestion will be available in the next update"

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

from predictive_utils import find_similar_transactions, TEXT_THRESHOLD, SEMANTIC_THRESHOLD

@main.route('/api/generate-insights', methods=['POST'])
@login_required
def generate_insights_api():
    try:
        # Get transactions for the current financial year
        company_settings = CompanySettings.query.filter_by(user_id=current_user.id).first()
        if not company_settings:
            return jsonify({'error': 'Please configure company settings first.'}), 400

        fy_dates = company_settings.get_financial_year()
        transactions = Transaction.query.filter(
            Transaction.user_id == current_user.id,
            Transaction.date.between(fy_dates['start_date'], fy_dates['end_date'])
        ).order_by(Transaction.date.desc()).all()

        # Format transactions for response
        transaction_data = [{
            'id': t.id,
            'date': t.date.strftime('%Y-%m-%d'),
            'description': t.description,
            'amount': float(t.amount),
            'category': t.account.category if t.account else 'Uncategorized'
        } for t in transactions]

        # Generate insights using AI
        insights_generator = FinancialInsightsGenerator()
        insights = insights_generator.generate_insights(transaction_data)

        return jsonify({
            'transactions': transaction_data,
            'insights': insights
        })

    except Exception as e:
        logger.error(f"Error generating AI insights: {str(e)}")
        return jsonify({'error': str(e)}), 500