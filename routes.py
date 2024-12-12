import logging
import os
from datetime import datetime
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, session, make_response, jsonify
)
from flask_login import (
    login_required, current_user, login_user, logout_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from weasyprint import HTML
import pandas as pd
from sqlalchemy import func

from app import db
from models import (
    User, Account, Transaction, UploadedFile, CompanySettings
)
from ai_utils import (
    predict_account, detect_transaction_anomalies,
    generate_financial_advice, forecast_expenses
)

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create blueprint
main = Blueprint('main', __name__)

# Configure pandas display options for debugging
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create blueprint
main = Blueprint('main', __name__)

# Configure secret key for session management
import os
if not os.environ.get('FLASK_SECRET_KEY'):
    os.environ['FLASK_SECRET_KEY'] = os.urandom(24).hex()

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
    anomalies = None

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
    
    # Perform anomaly detection on transactions
    try:
        from ai_utils import detect_transaction_anomalies
        anomalies = detect_transaction_anomalies(transactions)
        logger.info(f"Detected anomalies: {anomalies}")
    except Exception as e:
        logger.error(f"Error detecting anomalies: {str(e)}")
        anomalies = {"error": str(e)}
    
    return render_template('analyze.html', 
                         file=file,
                         accounts=accounts,
                         transactions=transactions,
                         bank_account_id=request.form.get('bank_account', type=int) or request.args.get('bank_account', type=int),
                         anomalies=anomalies)

@main.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    try:
        # Get list of uploaded files
        files = UploadedFile.query.filter_by(user_id=current_user.id).order_by(UploadedFile.upload_date.desc()).all()
        logger.info(f"Retrieved {len(files)} existing files for user {current_user.id}")
        
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
                
            # Log file details
            logger.info(f"File name: {file.filename}")
            logger.info(f"File content type: {file.content_type}")
            
            # Handle file upload POST request
            try:
                # Create uploaded file record first
                uploaded_file = UploadedFile(
                    filename=file.filename,
                    user_id=current_user.id
                )
                db.session.add(uploaded_file)
                db.session.commit()
                
                # Read file content in chunks with progress tracking
                chunk_size = 1000  # Process 1000 rows at a time
                total_rows = 0
                processed_rows = 0
                session['upload_progress'] = 0

                try:
                    # Configure progress tracking
                    session['upload_status'] = {
                        'filename': file.filename,
                        'total_rows': 0,
                        'processed_rows': 0,
                        'current_chunk': 0,
                        'status': 'counting'
                    }
                    
                    # First get total rows for progress tracking
                    if file.filename.endswith('.csv'):
                        total_rows = sum(1 for line in file) - 1  # Subtract header row
                        file.seek(0)  # Reset file pointer
                        df_iterator = pd.read_csv(file, chunksize=chunk_size)
                        logger.info(f"Processing CSV file with {total_rows} rows")
                    else:
                        # Use openpyxl for Excel files to support streaming
                        df = pd.read_excel(file, engine='openpyxl')
                        total_rows = len(df)
                        # Create chunk iterator for excel
                        df_iterator = [df[i:i + chunk_size] for i in range(0, len(df), chunk_size)]
                        logger.info(f"Processing Excel file with {total_rows} rows")
                    
                    # Update session with total rows
                    session['upload_status']['total_rows'] = total_rows
                    session['upload_status']['status'] = 'processing'
                    session.modified = True

                    # Initialize progress in session
                    session['upload_total_rows'] = total_rows
                    session['upload_filename'] = file.filename
                    logger.info(f"Started processing file: {file.filename}")
            
                    # Process each chunk with detailed progress tracking
                    for chunk_idx, chunk in enumerate(df_iterator):
                        # Clean and normalize column names
                        chunk.columns = chunk.columns.str.strip().str.lower()
                        processed_rows += len(chunk)
                        
                        # Update progress with detailed status
                        session['upload_status'].update({
                            'processed_rows': processed_rows,
                            'current_chunk': chunk_idx + 1,
                            'progress': int((processed_rows / total_rows) * 100),
                            'last_update': datetime.utcnow().isoformat()
                        })
                        session.modified = True
                        
                        logger.info(f"Processing chunk {chunk_idx + 1}/{(total_rows//chunk_size) + 1}, "
                                  f"Progress: {session['upload_status']['progress']}%, "
                                  f"Processed rows: {processed_rows}/{total_rows}")
                        
                        # Add a small delay to prevent database overload
                        if chunk_idx % 5 == 0:  # Every 5 chunks
                            db.session.commit()  # Commit current progress
                        
                        transactions_to_add = []
                        for _, row in chunk.iterrows():
                            try:
                                # Parse date with flexible format handling
                                date_str = str(row['date'])
                                try:
                                    parsed_date = pd.to_datetime(date_str)
                                except:
                                    # Try specific formats if automatic parsing fails
                                    date_formats = ['%Y%m%d', '%d/%m/%Y', '%m/%d/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m-%d-%Y']
                                    parsed_date = None
                                    for date_format in date_formats:
                                        try:
                                            parsed_date = pd.to_datetime(date_str, format=date_format)
                                            break
                                        except ValueError:
                                            continue
                                    
                                    if not parsed_date:
                                        logger.warning(f"Could not parse date: {date_str}")
                                        continue

                                # Create transaction object
                                transaction = Transaction(
                                    date=parsed_date,
                                    description=str(row['description']),
                                    amount=float(row['amount']),
                                    explanation='',
                                    user_id=current_user.id,
                                    file_id=uploaded_file.id
                                )
                                transactions_to_add.append(transaction)
                            except Exception as row_error:
                                logger.error(f"Error processing row: {row} - {str(row_error)}")
                                continue

                        # Batch save transactions for current chunk
                        if transactions_to_add:
                            try:
                                db.session.bulk_save_objects(transactions_to_add)
                                db.session.commit()
                                logger.info(f"Saved {len(transactions_to_add)} transactions from chunk {chunk_idx + 1}")
                            except Exception as save_error:
                                logger.error(f"Error saving chunk {chunk_idx + 1}: {str(save_error)}")
                                db.session.rollback()

                except Exception as e:
                    logger.error(f"Error reading file {file.filename}: {str(e)}")
                    flash(f"Error reading file: {str(e)}")
                    return redirect(url_for('main.upload'))
                
                flash('File uploaded and processed successfully')
                return redirect(url_for('main.analyze', file_id=uploaded_file.id))
            
            except Exception as e:
                logger.error(f"Error processing file: {str(e)}")
                db.session.rollback()
                flash('Error processing file')
                return redirect(url_for('main.upload'))
                
    except Exception as e:
        logger.error(f"Error in upload route: {str(e)}")
        flash('An error occurred during file upload')
        return redirect(url_for('main.upload'))
        
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

@main.route('/predict_account', methods=['POST'])
@login_required
def predict_account_route():
    """Handle prediction requests with improved error handling and logging"""
    try:
        # Validate request
        if not request.is_json:
            logger.warning("Invalid content type received")
            return jsonify({'error': 'Invalid content type. Expected JSON.'}), 400
            
        data = request.get_json()
        if not data:
            logger.warning("Empty request data received")
            return jsonify({'error': 'No data provided'}), 400
            
        description = data.get('description', '')
        explanation = data.get('explanation', '')
        
        if not description:
            logger.warning("Missing description in request")
            return jsonify({'error': 'Description is required'}), 400
            
        logger.info(f"Processing prediction request for description: {description}")
        
        # Get accounts
        accounts = Account.query.filter_by(user_id=current_user.id).all()
        if not accounts:
            logger.warning(f"No accounts found for user {current_user.id}")
            return jsonify({'error': 'No accounts available for prediction'}), 404
            
        account_data = [{
            'name': account.name,
            'category': account.category,
            'link': account.link,
            'id': account.id,
            'sub_category': account.sub_category
        } for account in accounts]
        
        logger.debug(f"Found {len(account_data)} accounts for prediction")
        
        # Get predictions with detailed error handling
        try:
            predictions = predict_account(description, explanation, account_data)
            if not predictions:
                logger.warning("No predictions generated")
                return jsonify({'error': 'No suitable predictions found'}), 404
                
            logger.info(f"Successfully generated {len(predictions)} predictions")
            return jsonify(predictions)
            
        except ValueError as ve:
            logger.error(f"Validation error in prediction: {str(ve)}")
            return jsonify({'error': str(ve)}), 400
            
        except Exception as pred_error:
            logger.error(f"Error during account prediction: {str(pred_error)}")
            return jsonify({
                'error': 'Failed to generate predictions',
                'details': str(pred_error)
            }), 500
            
    except Exception as e:
        logger.error(f"Unexpected error in prediction route: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500

@main.route('/expense-forecast')
@login_required
def expense_forecast():
    try:
        # Get current financial year transactions
        company_settings = CompanySettings.query.filter_by(user_id=current_user.id).first()
        if not company_settings:
            flash('Please configure company settings first.')
            return redirect(url_for('main.company_settings'))
        
        # Get financial year dates
        fy_dates = company_settings.get_financial_year()
        start_date = fy_dates['start_date']
        end_date = fy_dates['end_date']
        
        # Get transactions
        transactions = Transaction.query.filter(
            Transaction.user_id == current_user.id,
            Transaction.date.between(start_date, end_date)
        ).order_by(Transaction.date.desc()).all()
        
        # Format transactions for AI analysis
        transaction_data = [{
            'amount': t.amount,
            'description': t.description,
            'date': t.date.strftime('%Y-%m-%d'),
            'account_name': t.account.name if t.account else 'Uncategorized'
        } for t in transactions]
        
        # Get account information
        accounts = Account.query.filter_by(user_id=current_user.id).all()
        account_data = [{
            'name': acc.name,
            'category': acc.category,
            'balance': sum(t.amount for t in transactions if t.account_id == acc.id)
        } for acc in accounts]
        
        # Generate expense forecast
        forecast = forecast_expenses(transaction_data, account_data)
        
        # Prepare data for charts
        monthly_data = forecast['monthly_forecasts']
        monthly_labels = [str(m.get('month', '')) for m in monthly_data]
        monthly_amounts = [float(m.get('total_expenses', 0)) for m in monthly_data]
        
        # Calculate confidence intervals
        confidence_upper = []
        confidence_lower = []
        for m in monthly_data:
            base_amount = float(m.get('total_expenses', 0))
            variance = forecast.get('confidence_metrics', {}).get('variance_range', {'min': 0, 'max': 0})
            variance_max = float(variance.get('max', base_amount))
            variance_min = float(variance.get('min', base_amount))
            confidence_upper.append(variance_max)
            confidence_lower.append(variance_min)
        
        # Prepare category breakdown
        categories = {}
        for m in monthly_data:
            for cat in m.get('breakdown', []):
                category = cat.get('category', 'Other')
                amount = float(cat.get('amount', 0))
                if category not in categories:
                    categories[category] = []
                categories[category].append(amount)
        
        category_labels = list(categories.keys())
        category_amounts = [
            sum(amounts)/len(amounts) if amounts else 0 
            for amounts in categories.values()
        ]
        
        # Store the data in session for PDF generation
        session['forecast'] = forecast
        session['monthly_labels'] = monthly_labels
        session['monthly_amounts'] = monthly_amounts
        session['confidence_upper'] = confidence_upper
        session['confidence_lower'] = confidence_lower
        session['category_labels'] = category_labels
        session['category_amounts'] = category_amounts
        
        # Prepare template data
        template_data = {
            'forecast': forecast,
            'monthly_labels': monthly_labels,
            'monthly_amounts': monthly_amounts,
            'confidence_upper': confidence_upper,
            'confidence_lower': confidence_lower,
            'category_labels': category_labels,
            'category_amounts': category_amounts
        }
        
        return render_template(
            'expense_forecast.html',
            **template_data
        )
        
    except Exception as e:
        logger.error(f"Error generating expense forecast: {str(e)}")
        flash('Error generating expense forecast. Please try again.')
        return redirect(url_for('main.dashboard'))

@main.route('/export-forecast-pdf')
@login_required
def export_forecast_pdf():
    try:
        # Get company settings
        company_settings = CompanySettings.query.filter_by(user_id=current_user.id).first()
        if not company_settings:
            flash('Please configure company settings first.')
            return redirect(url_for('main.company_settings'))
            
        # Get forecast data from session
        forecast = session.get('forecast', {})
        monthly_labels = session.get('monthly_labels', [])
        monthly_amounts = session.get('monthly_amounts', [])
        confidence_upper = session.get('confidence_upper', [])
        confidence_lower = session.get('confidence_lower', [])
        category_labels = session.get('category_labels', [])
        category_amounts = session.get('category_amounts', [])
        
        if not forecast:
            flash('No forecast data available. Please generate a forecast first.')
            return redirect(url_for('main.expense_forecast'))
        
        # Render template to HTML
        html = render_template(
            'pdf_templates/forecast_pdf.html',
            forecast=forecast,
            monthly_labels=monthly_labels,
            monthly_amounts=monthly_amounts,
            confidence_upper=confidence_upper,
            confidence_lower=confidence_lower,
            category_labels=category_labels,
            category_amounts=category_amounts,
            company=company_settings,
            datetime=datetime,
            zip=zip
        )
        
        # Generate PDF
        pdf = HTML(string=html).write_pdf()
        
        # Create response
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = 'attachment; filename=expense_forecast.pdf'
        
        return response
        
    except Exception as e:
        logger.error(f"Error generating PDF: {str(e)}")
        flash('Error generating PDF report. Please try again.')
        return redirect(url_for('main.expense_forecast'))
        # Prepare template data
        template_data = {
            'forecast': forecast,
            'company': company_settings,
            'datetime': datetime,
            'monthly_labels': session.get('monthly_labels', []),
            'monthly_amounts': session.get('monthly_amounts', []),
            'confidence_upper': session.get('confidence_upper', []),
            'confidence_lower': session.get('confidence_lower', []),
            'category_labels': session.get('category_labels', []),
            'category_amounts': session.get('category_amounts', []),
            'zip': zip  # Required for template iteration
        }
        
        try:
            # Render template to HTML
            html_content = render_template(
                'pdf_templates/forecast_pdf.html',
                **template_data
            )
            
            # Generate PDF using WeasyPrint
            pdf = HTML(string=html_content).write_pdf()
            
            # Create response
            response = make_response(pdf)
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename=forecast_report_{datetime.now().strftime("%Y%m%d")}.pdf'
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating PDF: {str(e)}")
            flash('Error generating PDF report')
            return redirect(url_for('main.expense_forecast'))
            
    except Exception as e:
        logger.error(f"Error preparing template data: {str(e)}")
        flash('Error preparing report data')
        return redirect(url_for('main.expense_forecast'))

@main.route('/upload-progress')
@login_required
def upload_progress():
    """Get the current upload progress."""
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
            'last_update': status.get('last_update')
        })
        
    except Exception as e:
        logger.error(f"Error checking upload progress: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Error checking upload progress'
        }), 500

@main.route('/generate-pdf')
@login_required
def generate_pdf():
    """Generate and download a PDF report with financial forecasts."""
    try:
        # Get company settings and verify
        company_settings = CompanySettings.query.filter_by(user_id=current_user.id).first()
        if not company_settings:
            flash('Please configure company settings first.')
            return redirect(url_for('main.company_settings'))
            
        # Generate forecast data
        forecast_data = generate_forecast_data()  # Implement this function based on your needs
        
        # Create PDF from template
        html_content = render_template(
            'pdf/forecast_report.html',
            forecast=forecast_data,
            company=company_settings
        )
        
        # Generate PDF
        pdf = HTML(string=html_content).write_pdf()
        
        # Create response
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=forecast_report_{datetime.now().strftime("%Y%m%d")}.pdf'
        
        return response
        
    except Exception as e:
        logger.error(f"Error generating PDF: {str(e)}")
        flash('Error generating PDF report. Please try again.')
        return redirect(url_for('main.expense_forecast'))

@main.route('/financial-insights')
@login_required
def financial_insights():
    """Display financial insights and analysis."""
    try:
        # Get company settings for financial year
        company_settings = CompanySettings.query.filter_by(user_id=current_user.id).first()
        if not company_settings:
            flash('Please configure company settings first.')
            return redirect(url_for('main.company_settings'))
        
        # Get current financial year dates
        fy_dates = company_settings.get_financial_year()
        
        # Get transactions for analysis
        transactions = Transaction.query.filter(
            Transaction.user_id == current_user.id,
            Transaction.date >= fy_dates['start_date'],
            Transaction.date <= fy_dates['end_date']
        ).all()
        
        # Get accounts for the user
        accounts = Account.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).all()
        
        # Generate insights using AI
        insights = generate_financial_advice(
            transactions=[t.to_dict() for t in transactions],
            accounts=[a.to_dict() for a in accounts]
        )
        
        return render_template(
            'financial_insights.html',
            insights=insights,
            company=company_settings,
            fy_dates=fy_dates
        )
        
    except Exception as e:
        logger.error(f"Error generating financial insights: {str(e)}")
        flash('Error generating financial insights. Please try again.')
        return redirect(url_for('main.dashboard'))