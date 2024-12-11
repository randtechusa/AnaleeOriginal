from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import pandas as pd
import logging
import os
from app import db
from models import User, Account, Transaction, UploadedFile, CompanySettings

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
            # First save the user to get their ID
            db.session.add(user)
            db.session.commit()

            # Get template accounts from the first user (admin)
            template_user = User.query.filter(User.id != user.id).first()
            if template_user:
                template_accounts = Account.query.filter_by(user_id=template_user.id).all()
                # Copy accounts to new user
                for template_account in template_accounts:
                    new_account = Account(
                        link=template_account.link,
                        category=template_account.category,
                        sub_category=template_account.sub_category,
                        account_code=template_account.account_code,
                        name=template_account.name,
                        user_id=user.id,
                        is_active=template_account.is_active
                    )
                    db.session.add(new_account)
                db.session.commit()
                logger.info(f'Copied {len(template_accounts)} accounts to new user {user.username}')

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
        # Handle manual account addition
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
            flash(f'Error adding account: {str(e)}')
            db.session.rollback()
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
    # Get company settings for financial year
    company_settings = CompanySettings.query.filter_by(user_id=current_user.id).first()
    if not company_settings:
        flash('Please configure company settings first.')
        return redirect(url_for('main.company_settings'))
    
    # Get selected year from query params or use current year
    selected_year = request.args.get('year', type=int)
    current_date = datetime.utcnow()
    
    if not selected_year:
        # Calculate current financial year based on company settings
        if current_date.month > company_settings.financial_year_end:
            selected_year = current_date.year
        else:
            selected_year = current_date.year - 1
    
    # Calculate financial year date range
    fy_dates = company_settings.get_financial_year(current_date)
    start_date = fy_dates['start_date']
    end_date = fy_dates['end_date']
    
    # Get transactions for the selected financial year
    transactions = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        Transaction.date.between(start_date, end_date)
    ).order_by(Transaction.date.desc()).all()
    
    # Calculate totals
    total_income = sum(t.amount for t in transactions if t.amount > 0)
    total_expenses = abs(sum(t.amount for t in transactions if t.amount < 0))
    transaction_count = len(transactions)
    
    # Prepare monthly data
    monthly_data = {}
    for transaction in transactions:
        month_key = transaction.date.strftime('%Y-%m')
        if month_key not in monthly_data:
            monthly_data[month_key] = {'income': 0, 'expenses': 0}
        if transaction.amount > 0:
            monthly_data[month_key]['income'] += transaction.amount
        else:
            monthly_data[month_key]['expenses'] += abs(transaction.amount)
    
    # Sort months and prepare chart data
    sorted_months = sorted(monthly_data.keys())
    monthly_labels = [datetime.strptime(m, '%Y-%m').strftime('%b %Y') for m in sorted_months]
    monthly_income = [monthly_data[m]['income'] for m in sorted_months]
    monthly_expenses = [monthly_data[m]['expenses'] for m in sorted_months]
    
    # Prepare category data
    category_data = {}
    for transaction in transactions:
        if transaction.account and transaction.amount < 0:  # Only expenses
            category = transaction.account.category or 'Uncategorized'
            category_data[category] = category_data.get(category, 0) + abs(transaction.amount)
    
    # Sort categories by amount
    sorted_categories = sorted(category_data.items(), key=lambda x: x[1], reverse=True)
    category_labels = [cat[0] for cat in sorted_categories]
    category_amounts = [cat[1] for cat in sorted_categories]
    
    # Get available financial years
    financial_years = set()
    for t in Transaction.query.filter_by(user_id=current_user.id).all():
        if t.date.month > company_settings.financial_year_end:
            financial_years.add(t.date.year)
        else:
            financial_years.add(t.date.year - 1)
    financial_years = sorted(list(financial_years))
    
    # Get recent transactions
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

@main.route('/analyze/<int:file_id>', methods=['GET', 'POST'])
@login_required
def analyze(file_id):
    file = UploadedFile.query.filter_by(id=file_id, user_id=current_user.id).first_or_404()
    accounts = Account.query.filter_by(user_id=current_user.id).all()
    transactions = Transaction.query.filter_by(file_id=file_id, user_id=current_user.id).all()
    bank_account_id = None

    if request.method == 'POST':
        try:
            # Handle bank account selection
            bank_account_id = request.form.get('bank_account')
            if bank_account_id:
                bank_account_id = int(bank_account_id)
                
            for transaction in transactions:
                explanation_key = f'explanation_{transaction.id}'
                analysis_key = f'analysis_{transaction.id}'
                
                # Update transaction details
                if explanation_key in request.form:
                    transaction.explanation = request.form[explanation_key]
                if analysis_key in request.form:
                    account_id = request.form[analysis_key]
                    if account_id:  # Only update if a value was selected
                        transaction.account_id = int(account_id)
                        # Set the bank account for double-entry
                        if bank_account_id:
                            transaction.bank_account_id = bank_account_id
            
            db.session.commit()
            flash('Changes saved successfully', 'success')
        except Exception as e:
            logger.error(f"Error saving analysis changes: {str(e)}")
            db.session.rollback()
            flash('Error saving changes', 'error')
    
    return render_template('analyze.html', 
                         file=file,
                         accounts=accounts,
                         transactions=transactions)

@main.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    # Get list of uploaded files
    files = UploadedFile.query.filter_by(user_id=current_user.id).order_by(UploadedFile.upload_date.desc()).all()
    
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
            # Create uploaded file record first
            uploaded_file = UploadedFile(
                filename=file.filename,
                user_id=current_user.id
            )
            db.session.add(uploaded_file)
            db.session.commit()
            
            # Read file content
            if file.filename.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)
                
            # Clean and normalize column names
            df.columns = df.columns.str.strip().str.lower()
            logger.debug(f"Original columns in file: {df.columns.tolist()}")
            
            # Define required columns and their possible variations
            column_mappings = {
                'date': ['date', 'trans_date', 'transaction_date', 'trans date', 'transdate', 'dated', 'dt'],
                'description': ['description', 'desc', 'narrative', 'details', 'transaction', 'particulars', 'descr'],
                'amount': ['amount', 'amt', 'sum', 'value', 'debit/credit', 'transaction_amount', 'total']
            }
            
            # Find best matches for each required column
            column_matches = {}
            missing_columns = []
            
            for required_col, variations in column_mappings.items():
                # Log the current column we're looking for
                logger.debug(f"Looking for matches for {required_col}")
                logger.debug(f"Available columns: {df.columns.tolist()}")
                
                # First, check if the required column exists exactly as is
                if required_col in df.columns:
                    logger.debug(f"Found exact match for {required_col}")
                    column_matches[required_col] = required_col
                    continue
                
                # Then try variations
                found = False
                for col in df.columns:
                    # Try exact matches with variations
                    if col in variations:
                        logger.debug(f"Found variation match: {col} for {required_col}")
                        column_matches[required_col] = col
                        found = True
                        break
                    
                    # Try partial matches
                    if not found:
                        for var in variations:
                            if var in col or col in var:
                                logger.debug(f"Found partial match: {col} for {required_col} (variation: {var})")
                                column_matches[required_col] = col
                                found = True
                                break
                
                if not found:
                    logger.warning(f"No match found for {required_col}")
                    missing_columns.append(required_col)
            
            if missing_columns:
                flash(f'Missing required columns: {", ".join(missing_columns)}. Found columns: {", ".join(df.columns)}')
                return redirect(url_for('main.upload'))

            # Rename columns to standard names
            df = df.rename(columns=column_matches)
            
            # Process each row
            for _, row in df.iterrows():
                try:
                    date_str = str(row['date'])
                    try:
                        # First try parsing without explicit format
                        parsed_date = pd.to_datetime(date_str)
                    except:
                        # If that fails, try specific formats
                        date_formats = ['%Y%m%d', '%d/%m/%Y', '%m/%d/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m-%d-%Y']
                        parsed_date = None
                        
                        for date_format in date_formats:
                            try:
                                parsed_date = pd.to_datetime(date_str, format=date_format)
                                break
                            except ValueError:
                                continue
                        
                        if parsed_date is None:
                            logger.warning(f"Could not parse date: {date_str}")
                            continue
                    
                    transaction = Transaction(
                        date=parsed_date,
                        description=str(row['description']),
                        amount=float(row['amount']),
                        explanation='',  # Initially empty
                        user_id=current_user.id,
                        file_id=uploaded_file.id
                    )
                    db.session.add(transaction)
                except Exception as row_error:
                    logger.error(f"Error processing row: {row} - {str(row_error)}")
                    continue
            
            db.session.commit()
            flash('File uploaded and processed successfully')
            return redirect(url_for('main.analyze', file_id=uploaded_file.id))
            
        except Exception as e:
            logger.error(f'Error processing file: {str(e)}')
            db.session.rollback()
            flash(f'Error processing file: {str(e)}')
            
    return render_template('upload.html', files=files)

@main.route('/file/<int:file_id>/delete', methods=['POST'])
@login_required
def delete_file(file_id):
    file = UploadedFile.query.filter_by(id=file_id, user_id=current_user.id).first_or_404()
    try:
        # Delete associated transactions first
        Transaction.query.filter_by(file_id=file.id).delete()
        # Then delete the file record
        db.session.delete(file)
        db.session.commit()
        flash('File and associated transactions deleted successfully')
    except Exception as e:
        logger.error(f'Error deleting file: {str(e)}')
        flash('Error deleting file')
        db.session.rollback()
    return redirect(url_for('main.upload'))

@main.route('/output')
@login_required
def output():
    trial_balance = []
    categories = []
    
    # Get company settings for financial year
    company_settings = CompanySettings.query.filter_by(user_id=current_user.id).first()
    if not company_settings:
        flash('Please configure company settings first.')
        return redirect(url_for('main.company_settings'))
    
    # Get selected year from query params or use current year
    selected_year = request.args.get('financial_year', type=int)
    current_date = datetime.utcnow()
    
    if not selected_year:
        # Calculate current financial year based on company settings
        if current_date.month > company_settings.financial_year_end:
            selected_year = current_date.year
        else:
            selected_year = current_date.year - 1
    
    # Get available financial years
    financial_years = set()
    for t in Transaction.query.filter_by(user_id=current_user.id).all():
        if t.date.month > company_settings.financial_year_end:
            financial_years.add(t.date.year)
        else:
            financial_years.add(t.date.year - 1)
    financial_years = sorted(list(financial_years))
    
    # Get all unique categories for the filter dropdown
    categories = db.session.query(Account.category).distinct().all()
    categories = [cat[0] for cat in categories if cat[0]]  # Remove None values
    
    # Calculate financial year date range
    start_date = datetime(selected_year, company_settings.financial_year_end + 1, 1)
    if company_settings.financial_year_end == 12:
        end_date = datetime(selected_year + 1, 1, 1)
    else:
        end_date = datetime(selected_year + 1, company_settings.financial_year_end + 1, 1)
    
    # Build the transaction query with filters
    query = Transaction.query.filter_by(user_id=current_user.id)
    
    # Apply financial year filter
    query = query.filter(Transaction.date >= start_date, Transaction.date < end_date)
    
    # Apply additional date filters if provided
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    if date_from:
        query = query.filter(Transaction.date >= datetime.strptime(date_from, '%Y-%m-%d'))
    if date_to:
        query = query.filter(Transaction.date <= datetime.strptime(date_to, '%Y-%m-%d'))
        
    # Get all transactions matching the filters
    transactions = query.all()
    
    # Filter by category if provided
    category_filter = request.args.get('category')
    
    for transaction in transactions:
        # Add the main account entry
        if transaction.account:
            # Skip if category filter is active and doesn't match
            if category_filter and transaction.account.category != category_filter:
                continue
            
            account = transaction.account
            account_info = next((item for item in trial_balance if item['account_name'] == account.name), None)
            if account_info is None:
                account_info = {
                    'account_name': account.name,
                    'category': account.category,
                    'sub_category': account.sub_category,
                    'link': account.link,
                    'amount': 0
                }
                trial_balance.append(account_info)
            account_info['amount'] += transaction.amount
        
        # Add the corresponding bank account entry (double-entry)
        if transaction.bank_account:
            # Skip if category filter is active and doesn't match
            if category_filter and transaction.bank_account.category != category_filter:
                continue
            
            bank_account = transaction.bank_account
            bank_info = next((item for item in trial_balance if item['account_name'] == bank_account.name), None)
            if bank_info is None:
                bank_info = {
                    'account_name': bank_account.name,
                    'category': bank_account.category,
                    'sub_category': bank_account.sub_category,
                    'link': bank_account.link,
                    'amount': 0
                }
                trial_balance.append(bank_info)
            # Reverse the amount for the bank account (double-entry)
            bank_info['amount'] -= transaction.amount
    
    return render_template('output.html', 
                         trial_balance=trial_balance,
                         categories=categories,
                         financial_years=financial_years,
                         current_year=selected_year)
