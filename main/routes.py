"""Main routes for the application"""
import logging
import os
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from models import db, Account, AdminChartOfAccounts, Transaction, UploadedFile # Added UploadedFile model import


main = Blueprint('main', __name__)

@main.route('/edit_account/<int:account_id>', methods=['GET', 'POST'])
@login_required
def edit_account(account_id):
    """Edit an existing account"""
    account = Account.query.get_or_404(account_id)

    if account.user_id != current_user.id:
        abort(403)

    if request.method == 'POST':
        account.name = request.form.get('name')
        account.category = request.form.get('category')
        account.sub_category = request.form.get('sub_category')

        try:
            db.session.commit()
            flash('Account updated successfully', 'success')
            return redirect(url_for('main.settings'))
        except Exception as e:
            db.session.rollback()
            flash('Error updating account', 'error')

    return render_template('edit_account.html', account=account)

# Placeholder for PredictiveFeatures class - needs to be implemented separately
class PredictiveFeatures:
    def suggest_account(self, description, explanation):
        # Replace with actual prediction logic
        # This is a placeholder, replace with your actual implementation
        suggestions = [{'account': 'Asset', 'confidence': 0.8}, {'account': 'Liability', 'confidence': 0.2}]
        return suggestions

logger = logging.getLogger(__name__)


@main.route('/')
@main.route('/index')
@login_required
def index():
    return render_template('index.html')

@main.route('/analyze_list')
@login_required
def analyze_list():
    """Route for analyze data menu - protected core functionality"""
    return render_template('analyze_list.html')

@main.route('/dashboard')
@login_required 
def dashboard():
    """Main dashboard route"""
    try:
        # Get transactions and calculate totals
        transactions = Transaction.query.filter_by(user_id=current_user.id).all()

        total_income = 0
        total_expenses = 0
        for transaction in transactions:
            if transaction.amount > 0:
                total_income += transaction.amount
            else:
                total_expenses += abs(transaction.amount)

        return render_template('dashboard.html',
                            total_income=total_income,
                            total_expenses=total_expenses,
                            transaction_count=len(transactions),
                            transactions=transactions[:5],  # Latest 5 transactions
                            monthly_labels=[],  # Add chart data as needed
                            monthly_income=[],
                            monthly_expenses=[],
                            category_labels=[],
                            category_amounts=[])
    except Exception as e:
        logger.error(f"Error in dashboard route: {str(e)}")
        flash('Error loading dashboard data', 'error')
        return render_template('dashboard.html',
                            total_income=0,
                            total_expenses=0,
                            transaction_count=0,
                            transactions=[],
                            monthly_labels=[],
                            monthly_income=[],
                            monthly_expenses=[],
                            category_labels=[],
                            category_amounts=[])

@main.route('/icountant', methods=['GET', 'POST'])
@login_required
def icountant():
    """iCountant Assistant route"""
    try:
        logger.debug("Accessing iCountant route")
        return render_template('icountant.html')
    except Exception as e:
        logger.error(f"Error in icountant route: {str(e)}", exc_info=True)
        flash('Error accessing iCountant Assistant', 'error')
        return redirect(url_for('main.dashboard'))

@main.route('/icountant_interface', methods=['GET', 'POST'])
@login_required
def icountant_interface():
    """Handle iCountant interface interactions"""
    try:
        return render_template('icountant.html')
    except Exception as e:
        logger.error(f"Error in iCountant interface: {str(e)}", exc_info=True)
        flash('Error processing request', 'error')
        return redirect(url_for('main.dashboard'))

@main.route('/upload', methods=['GET', 'POST'])
@login_required 
def upload():
    logger.info('Starting upload process')
    # Ensure upload directory exists
    try:
        upload_folder = current_app.config['UPLOAD_FOLDER']
        logger.debug(f'Using upload folder: {upload_folder}')
        os.makedirs(upload_folder, exist_ok=True)
        logger.info('Upload folder verified/created successfully')
    """Route for uploading data with improved error handling"""
    try:
        from .forms import UploadForm
        form = UploadForm()
        files = UploadedFile.query.filter_by(user_id=current_user.id).order_by(UploadedFile.upload_date.desc()).all()

        if request.method == 'POST':
            if not form.validate_on_submit():
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'error': 'Form validation failed'}), 400
                flash('Please ensure all fields are filled correctly', 'error')
                return render_template('upload.html', form=form, files=files)

            if not form.file.data:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'error': 'No file selected'}), 400
                flash('Please select a file to upload', 'error')
                return render_template('upload.html', form=form, files=files)

            try:
                logger.debug('Processing file upload')
                file = form.file.data
                if not file:
                    logger.error('No file provided in request')
                    raise ValueError('No file selected')
                    
                filename = secure_filename(file.filename)
                logger.debug(f'Secured filename: {filename}')
                upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], str(current_user.id))
                os.makedirs(upload_path, exist_ok=True)
                file_path = os.path.join(upload_path, filename)

                # Save file with timeout handling
                file.save(file_path)

                upload = UploadedFile(
                    filename=filename,
                    filepath=file_path,
                    user_id=current_user.id
                )
                db.session.add(upload)
                db.session.commit()

                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': True})
                flash('File uploaded successfully', 'success')
                return redirect(url_for('main.upload'))

            except Exception as e:
                logger.error(f"Upload error: {str(e)}")
                error_message = str(e)
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'success': False,
                        'error': error_message
                    }), 500
                flash(error_message, 'error')
                return render_template('upload.html', form=form, files=files)

        return render_template('upload.html', form=form, files=files)

    except Exception as e:
        logger.error(f"Unexpected error in upload route: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500
        flash('An unexpected error occurred', 'error')
        return render_template('upload.html', form=form, files=[])

@main.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Protected Chart of Accounts management"""
    try:
        if not current_user.is_authenticated:
            flash('Please log in to access Chart of Accounts', 'warning')
            return redirect(url_for('auth.login'))

        # Get user accounts and system accounts
        user_accounts = Account.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).order_by(Account.category, Account.name).all()

        system_accounts = AdminChartOfAccounts.query.order_by(
            AdminChartOfAccounts.category,
            AdminChartOfAccounts.name
        ).all()

        return render_template('settings.html',
                             accounts=user_accounts,
                             system_accounts=system_accounts)

        if request.method == 'POST':
            if not request.form.get('name') or not request.form.get('category'):
                flash('Account name and category are required', 'error')
                return redirect(url_for('main.settings'))

            account = Account(
                link=request.form.get('link', request.form['name']),
                name=request.form['name'],
                category=request.form['category'],
                sub_category=request.form.get('sub_category', ''),
                account_code=request.form.get('account_code', ''),
                user_id=current_user.id
            )
            db.session.add(account)
            db.session.commit()
            flash('Account added successfully', 'success')

        # Get user's accounts
        accounts = Account.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).order_by(Account.category, Account.name).all()

        # Get system-wide Chart of Accounts for reference
        system_accounts = AdminChartOfAccounts.query.order_by(
            AdminChartOfAccounts.category, 
            AdminChartOfAccounts.name
        ).all()

        return render_template(
            'settings.html',
            accounts=accounts,
            system_accounts=system_accounts
        )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Settings access error: {str(e)}")
        flash('Error accessing Chart of Accounts. Please try again.', 'error')
        return redirect(url_for('main.dashboard'))

@main.route('/admin_dashboard')
@login_required
def admin_dashboard():
    return render_template('admin/dashboard.html')

@main.route('/company_settings')
@login_required
def company_settings():
    """Company settings route"""
    try:
        logger.debug("Accessing company settings route")
        return render_template('company_settings.html')
    except Exception as e:
        logger.error(f"Error in company settings route: {str(e)}", exc_info=True)
        flash('Error accessing company settings', 'error')
        return redirect(url_for('main.dashboard'))

@main.route('/financial_insights')
@login_required
def financial_insights():
    """Financial insights dashboard route"""
    try:
        return render_template('financial_insights.html', financial_advice={})
    except Exception as e:
        logger.error(f"Error in financial insights route: {str(e)}", exc_info=True)
        flash('Error accessing Financial Insights', 'error')
        return redirect(url_for('main.dashboard'))

@main.route('/analyze/suggest-account', methods=['POST'])
@login_required
def suggest_account():
    """ASF: Get account suggestions with enhanced error handling"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        description = data.get('description', '').strip()
        explanation = data.get('explanation', '').strip()

        if not description:
            return jsonify({'success': False, 'error': 'Description required'}), 400

        predictor = PredictiveFeatures()
        suggestions = predictor.suggest_account(description, explanation)

        return jsonify(suggestions)

    except Exception as e:
        logger.error(f"Error in suggest_account route: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
from flask import abort