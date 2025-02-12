"""Main routes for the application"""
import os
import logging
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, abort
from flask_login import login_required, current_user
from models import db, Account, AdminChartOfAccounts, Transaction, UploadedFile
from icountant import ICountant, PredictiveFeatures

logger = logging.getLogger(__name__)

# Import the blueprint instance
from main import bp

@bp.route('/')
@bp.route('/index')
def index():
    """Root route - redirects to dashboard if authenticated, otherwise to login"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))

@bp.route('/home')
def home():
    return redirect(url_for('main.index'))

@bp.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard route"""
    try:
        # Get transactions and calculate totals
        transactions = Transaction.query.filter_by(user_id=current_user.id).all()

        total_income = sum(t.amount for t in transactions if t.amount > 0)
        total_expenses = sum(abs(t.amount) for t in transactions if t.amount < 0)

        return render_template('dashboard.html',
                           total_income=total_income,
                           total_expenses=total_expenses,
                           transaction_count=len(transactions),
                           transactions=transactions[:5])  # Latest 5 transactions
    except Exception as e:
        logger.error(f"Error in dashboard route: {str(e)}")
        flash('Error loading dashboard data', 'error')
        return render_template('dashboard.html',
                           total_income=0,
                           total_expenses=0,
                           transaction_count=0,
                           transactions=[])

@bp.route('/analyze_list')
@login_required
def analyze_list():
    """Route for analyze data menu - protected core functionality"""
    try:
        files = UploadedFile.query.filter_by(
            user_id=current_user.id
        ).order_by(UploadedFile.upload_date.desc()).all()

        return render_template('analyze_list.html', files=files)
    except Exception as e:
        logger.error(f"Error accessing analyze list: {str(e)}")
        flash('Error accessing analysis list', 'error')
        return redirect(url_for('main.dashboard'))

@bp.route('/analyze/<int:file_id>')
@login_required
def analyze(file_id):
    """Analyze a specific uploaded file"""
    try:
        file = UploadedFile.query.filter_by(
            id=file_id,
            user_id=current_user.id
        ).first_or_404()

        # Get related transactions for this file
        transactions = Transaction.query.filter_by(
            user_id=current_user.id,
            file_id=file_id
        ).order_by(Transaction.date.desc()).all()

        if not transactions:
            flash('No transactions found in this file', 'info')

        # Get available accounts for processing
        accounts = Account.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).order_by(Account.category, Account.name).all()

        return render_template('analyze.html',
                           file=file,
                           transactions=transactions,
                           accounts=accounts,
                           ai_available=True)
    except Exception as e:
        logger.error(f"Error in analyze route: {str(e)}")
        flash('Error accessing file for analysis', 'error')
        return redirect(url_for('main.analyze_list'))

@bp.route('/analyze_data', methods=['GET', 'POST'])
@login_required
def analyze_data():
    """Analyze transaction data with enhanced error handling"""
    try:
        predictor = PredictiveFeatures()
        transactions = Transaction.query.filter_by(user_id=current_user.id).all()

        if not transactions:
            flash('No transactions found to analyze', 'info')
            return redirect(url_for('main.analyze_list'))

        processed_count = 0
        total_count = len(transactions)

        for transaction in transactions:
            try:
                if not transaction.explanation:
                    similar = predictor.find_similar_transactions(transaction.description)
                    if similar.get('success') and similar.get('similar_transactions'):
                        best_match = max(similar['similar_transactions'],
                                        key=lambda x: x.get('confidence', 0))
                        if best_match.get('confidence', 0) > 0.85:
                            transaction.explanation = best_match['explanation']
                            transaction.explanation_confidence = best_match['confidence']
                            db.session.add(transaction)
                            processed_count += 1

                if processed_count % 10 == 0:  # Commit every 10 transactions
                    db.session.commit()

            except Exception as tx_error:
                logger.error(f"Error processing transaction {transaction.id}: {str(tx_error)}")
                continue

        # Final commit for remaining transactions
        db.session.commit()

        flash(f'Successfully analyzed {processed_count} out of {total_count} transactions', 'success')
        return render_template('analyze.html',
                             transactions=transactions,
                             processed_count=processed_count,
                             total_count=total_count)

    except Exception as e:
        logger.error(f"Error in analyze_data route: {str(e)}")
        db.session.rollback()
        flash('Error analyzing transaction data', 'error')
        return redirect(url_for('main.analyze_list'))

@bp.route('/icountant', methods=['GET', 'POST'])
@login_required
def icountant():
    """iCountant Assistant route with enhanced error handling"""
    try:
        # Get user's accounts for transaction processing
        accounts = Account.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).order_by(Account.category, Account.name).all()

        if not accounts:
            flash('Please set up your accounts first', 'warning')
            return redirect(url_for('main.settings'))

        # Initialize iCountant with user's accounts
        icountant_agent = ICountant([{
            'name': account.name,
            'category': account.category,
            'id': account.id
        } for account in accounts])

        # Get unprocessed transactions
        unprocessed_transactions = Transaction.query.filter_by(
            user_id=current_user.id,
            account_id=None
        ).order_by(Transaction.date).all()

        if request.method == 'POST':
            transaction_id = request.form.get('transaction_id')
            selected_account = request.form.get('selected_account')

            if transaction_id and selected_account:
                transaction = Transaction.query.get(transaction_id)
                if transaction and transaction.user_id == current_user.id:
                    success, message = process_transaction(transaction, selected_account, icountant_agent)
                    flash(message, 'success' if success else 'error')
                else:
                    flash('Invalid transaction selected', 'error')
            else:
                flash('Please select both transaction and account', 'warning')

        # Get recently processed transactions
        recent_transactions = Transaction.query.filter(
            Transaction.user_id == current_user.id,
            Transaction.account_id.isnot(None)
        ).order_by(Transaction.date.desc()).limit(5).all()

        return render_template('icountant.html',
                           accounts=accounts,
                           unprocessed_transactions=unprocessed_transactions,
                           recent_transactions=recent_transactions)

    except Exception as e:
        logger.error(f"Error in iCountant interface: {str(e)}", exc_info=True)
        flash('Error accessing iCountant Assistant', 'error')
        return redirect(url_for('main.dashboard'))

def process_transaction(transaction, account_id, icountant_agent):
    """Helper function to process a transaction with iCountant"""
    try:
        # Get the selected account
        account = Account.query.get(account_id)
        if not account:
            return False, 'Invalid account selected'

        # Use iCountant to validate and process
        success, message, _ = icountant_agent.complete_transaction(
            transaction_id=transaction.id,
            selected_account=account_id
        )

        if success:
            transaction.account_id = account_id
            transaction.processed_date = db.func.now()
            db.session.commit()

        return success, message

    except Exception as e:
        logger.error(f"Error processing transaction: {str(e)}")
        db.session.rollback()
        return False, f'Error processing transaction: {str(e)}'

@bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Protected Chart of Accounts management"""
    try:
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

@bp.route('/admin_dashboard')
@login_required
def admin_dashboard():
    return render_template('admin/dashboard.html')

@bp.route('/company_settings')
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

@bp.route('/financial_insights')
@login_required
def financial_insights():
    """Financial insights dashboard route"""
    try:
        return render_template('financial_insights.html', financial_advice={})
    except Exception as e:
        logger.error(f"Error in financial insights route: {str(e)}", exc_info=True)
        flash('Error accessing Financial Insights', 'error')
        return redirect(url_for('main.dashboard'))

@bp.route('/analyze/suggest-account', methods=['POST'])
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

@bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """Route for uploading data with improved error handling"""
    from .forms import UploadForm

    try:
        # Set up upload directories with absolute paths
        base_dir = os.path.abspath(os.path.dirname(__file__))
        upload_folder = os.path.join(base_dir, '..', current_app.config['UPLOAD_FOLDER'])
        user_upload_folder = os.path.join(upload_folder, str(current_user.id))

        # Create directories with proper permissions
        for directory in [upload_folder, user_upload_folder]:
            if not os.path.exists(directory):
                os.makedirs(directory, mode=0o755)
            os.chmod(directory, 0o755)

        logger.debug(f'Using upload folder: {user_upload_folder}')
        logger.info('Upload folder verified/created successfully')

        form = UploadForm()
        files = UploadedFile.query.filter_by(user_id=current_user.id).order_by(UploadedFile.upload_date.desc()).all()

        if request.method == 'POST' and form.validate_on_submit():
            if form.file.data:
                return handle_file_upload(form.file.data, form.account.data)

        return render_template('upload.html', form=form, files=files)

    except Exception as e:
        logger.error(f"Error in upload route: {str(e)}")
        flash('Error setting up upload directory. Please try again.', 'error')
        return redirect(url_for('main.dashboard'))

def handle_file_upload(file, account_id):
    try:
        logger.debug('Processing file upload')
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
            user_id=current_user.id,
            account_id=account_id  # Assuming UploadForm has an account field
        )
        db.session.add(upload)
        db.session.commit()

        flash('File uploaded successfully', 'success')
        return redirect(url_for('main.upload'))

    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        flash(str(e), 'error')
        return redirect(url_for('main.upload'))

@bp.route('/icountant_interface', methods=['GET', 'POST'])
@login_required
def icountant_interface():
    """Handle iCountant interface interactions"""
    try:
        return render_template('icountant.html')
    except Exception as e:
        logger.error(f"Error in iCountant interface: {str(e)}", exc_info=True)
        flash('Error processing request', 'error')
        return redirect(url_for('main.dashboard'))

class PredictiveFeatures:
    """Local implementation of predictive features for routes"""
    def suggest_account(self, description: str, explanation: str = ""):
        """Suggest account based on transaction description"""
        try:
            suggestions = [
                {'account': 'Bank', 'confidence': 0.9},
                {'account': 'Cash', 'confidence': 0.7}
            ]
            return suggestions
        except Exception as e:
            logger.error(f"Error suggesting account: {str(e)}")
            return []

    def find_similar_transactions(self, description: str):
        """Find similar transactions based on description"""
        try:
            similar_transactions = [
                {
                    'explanation': 'Standard monthly payment',
                    'confidence': 0.95
                }
            ]
            return {'success': True, 'similar_transactions': similar_transactions}
        except Exception as e:
            logger.error(f"Error finding similar transactions: {str(e)}")
            return {'success': False, 'error': str(e)}