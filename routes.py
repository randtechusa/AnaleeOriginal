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
import logging
import os
import pandas as pd

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

@main.route('/predict_account', methods=['POST'])
@login_required
def predict_account_route():
    try:
        data = request.get_json()
        description = data.get('description', '')
        explanation = data.get('explanation', '')
        
        # Get all available accounts for the current user
        accounts = Account.query.filter_by(user_id=current_user.id).all()
        account_data = [{
            'name': account.name,
            'category': account.category,
            'link': account.link,
            'id': account.id,
            'sub_category': account.sub_category
        } for account in accounts]
        
        # Get predictions
        predictions = predict_account(description, explanation, account_data)
        
        return jsonify(predictions)
    except Exception as e:
        logger.error(f"Error in account prediction route: {str(e)}")
        return jsonify({'error': str(e)}), 500
    return redirect(url_for('main.upload'))

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
        from weasyprint import HTML
        from flask import make_response
        from datetime import datetime
        import os
        
        # Get company settings
        company_settings = CompanySettings.query.filter_by(user_id=current_user.id).first()
        if not company_settings:
            flash('Please configure company settings first.')
            return redirect(url_for('main.company_settings'))
            
        # Get forecast data from session
        forecast_data = session.get('forecast', {})
        if not forecast_data:
            flash('No forecast data available. Please generate a forecast first.')
            return redirect(url_for('main.expense_forecast'))
            
        # Generate the HTML content
        html_content = render_template(
            'pdf_templates/forecast_pdf.html',
            company=company_settings,
            datetime=datetime,
            forecast=forecast_data,
            monthly_labels=session.get('monthly_labels', []),
            monthly_amounts=session.get('monthly_amounts', []),
            confidence_upper=session.get('confidence_upper', []),
            confidence_lower=session.get('confidence_lower', []),
            category_labels=session.get('category_labels', []),
            category_amounts=session.get('category_amounts', []),
            zip=zip  # Required for template iteration
        )
        
        # Create PDF
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
    try:
        # Get company settings for financial year
        company_settings = CompanySettings.query.filter_by(user_id=current_user.id).first()
        if not company_settings:
            flash('Please configure company settings first.')
            return redirect(url_for('main.company_settings'))
        
        # Get current financial year dates
        fy_dates = company_settings.get_financial_year()
        start_date = fy_dates['start_date']
        end_date = fy_dates['end_date']
        
        # Get transactions for the current financial year
        transactions = Transaction.query.filter(
            Transaction.user_id == current_user.id,
            Transaction.date.between(start_date, end_date)
        ).order_by(Transaction.date.desc()).all()
        
        # Format transactions for AI analysis
        transaction_data = [{
            'amount': t.amount,
            'description': t.description,
            'account_name': t.account.name if t.account else 'Uncategorized'
        } for t in transactions]
        
        # Get account information
        accounts = Account.query.filter_by(user_id=current_user.id).all()
        account_data = [{
            'name': acc.name,
            'category': acc.category,
            'balance': sum(t.amount for t in acc.transactions)
        } for acc in accounts]
        
        # Generate financial advice and expense forecasts
        from ai_utils import generate_financial_advice, forecast_expenses
        financial_advice = generate_financial_advice(transaction_data, account_data)
        expense_forecast = forecast_expenses(transaction_data, account_data)
        
        return render_template(
            'financial_insights.html',
            financial_advice=financial_advice,
            expense_forecast=expense_forecast,
            transactions=transactions[:10],  # Show recent transactions
            accounts=accounts
        )
        
    except Exception as e:
        logger.error(f"Error generating financial insights: {str(e)}")
        flash('Error generating financial insights. Please try again.')
        return redirect(url_for('main.dashboard'))
@main.route('/output')
@login_required
def output():
    try:
        # Get company settings for financial year
        company_settings = CompanySettings.query.filter_by(user_id=current_user.id).first()
        if not company_settings:
            flash('Please configure company settings first.')
            return redirect(url_for('main.company_settings'))
        
        logger.info(f"Company settings found for user {current_user.id}, FY end month: {company_settings.financial_year_end}")
        
        # Get selected year from query params or use current year
        selected_year = request.args.get('financial_year', type=int)
        current_date = datetime.utcnow()
        
        # If no year selected, calculate current financial year
        if not selected_year:
            current_fy = company_settings.get_financial_year(date=current_date)
            selected_year = current_fy['start_year']
            logger.debug(f"No year selected, using current FY starting {selected_year}")
        
        # Get available financial years from transactions
        financial_years = set()
        transactions_query = Transaction.query.filter_by(user_id=current_user.id)
        transactions = transactions_query.all()
        
        for transaction in transactions:
            # Get the financial year for each transaction
            fy = company_settings.get_financial_year(date=transaction.date)
            financial_years.add(fy['start_year'])
        
        financial_years = sorted(list(financial_years))
        if not financial_years and selected_year:
            financial_years = [selected_year]
            logger.debug("No transactions found, using selected year only")
        
        logger.info(f"Available financial years: {financial_years}")
        logger.info(f"Selected year: {selected_year}")
        
        # Get financial year dates for the selected year
        fy_dates = company_settings.get_financial_year(year=selected_year)
        start_date = fy_dates['start_date']
        end_date = fy_dates['end_date']
        
        logger.info(f"Calculated FY period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
        # Get transactions for the selected financial year
        transactions = transactions_query.filter(
            Transaction.date >= start_date,
            Transaction.date <= end_date
        ).all()
        
        logger.info(f"Found {len(transactions)} transactions in selected period")
        
        # Initialize account balances
        account_balances = {}
        
        # Process transactions to build trial balance
        for transaction in transactions:
            logger.debug(f"Processing transaction: {transaction.id}, date: {transaction.date}, amount: {transaction.amount}")
            
            # Process main account entry
            if transaction.account:
                account = transaction.account
                if account.name not in account_balances:
                    account_balances[account.name] = {
                        'account_name': account.name,
                        'category': account.category,
                        'sub_category': account.sub_category,
                        'link': account.link,
                        'amount': 0
                    }
                account_balances[account.name]['amount'] += transaction.amount
                logger.debug(f"Updated balance for {account.name}: {account_balances[account.name]['amount']}")
            
            # Process bank account entry (double-entry)
            if transaction.bank_account:
                bank_account = transaction.bank_account
                if bank_account.name not in account_balances:
                    account_balances[bank_account.name] = {
                        'account_name': bank_account.name,
                        'category': bank_account.category,
                        'sub_category': bank_account.sub_category,
                        'link': bank_account.link,
                        'amount': 0
                    }
                account_balances[bank_account.name]['amount'] -= transaction.amount
                logger.debug(f"Updated balance for {bank_account.name}: {account_balances[bank_account.name]['amount']}")
        
        # Convert account_balances to list and sort by category and account name
        trial_balance = sorted(
            account_balances.values(),
            key=lambda x: (x['category'] or '', x['account_name'])
        )
        
        # Log debug information
        logger.debug(f"Number of accounts in trial balance: {len(trial_balance)}")
        logger.debug(f"Trial balance total: {sum(item['amount'] for item in trial_balance)}")
        
        return render_template('output.html',
                            trial_balance=trial_balance,
                            financial_years=financial_years,
                            current_year=selected_year)
                            
    except Exception as e:
        logger.error(f"Error generating trial balance: {str(e)}")
        logger.exception("Full stack trace:")
        flash('Error generating trial balance. Please try again.')
        return redirect(url_for('main.dashboard'))

# Removed duplicate implementation of export_forecast_pdf
# The primary implementation is maintained above at line 649