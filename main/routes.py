"""Main routes for the application"""
import logging
import os
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, abort
from flask_login import login_required, current_user
from models import db, Account, AdminChartOfAccounts, Transaction, UploadedFile
from icountant import ICountant, PredictiveFeatures

main = Blueprint('main', __name__)
logger = logging.getLogger(__name__)

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

    def find_similar_transactions(self, description):
        #  Implementation to find similar transactions based on description.
        # This is a placeholder, replace with your actual implementation.  Should return a dictionary
        # Example: {'success': True, 'similar_transactions': [{'explanation': 'Example explanation', 'confidence': 0.9}]}
        # or {'success': False, 'error': 'No similar transactions found'}

        # Replace this with your actual logic
        similar_transactions = [{'explanation': 'This is a similar transaction', 'confidence': 0.95}]
        return {'success': True, 'similar_transactions': similar_transactions}



@main.route('/')
@main.route('/index')
@login_required
def index():
    return render_template('index.html')

@main.route('/analyze_list')
@login_required
def analyze_list():
    """Route for analyze data menu - protected core functionality"""
    try:
        files = UploadedFile.query.filter_by(user_id=current_user.id).order_by(UploadedFile.upload_date.desc()).all()
        return render_template('analyze_list.html', files=files)
    except Exception as e:
        logger.error(f"Error accessing analyze list: {str(e)}")
        flash('Error accessing analysis list', 'error')
        return redirect(url_for('main.dashboard'))

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

@main.route('/analyze/<int:file_id>')
@login_required
def analyze(file_id):
    """Analyze a specific uploaded file"""
    try:
        if not file_id:
            flash('Invalid file ID', 'error')
            return redirect(url_for('main.analyze_list'))

        file = UploadedFile.query.get_or_404(file_id)
        if not os.path.exists(file.filepath):
            flash('File not found on server', 'error')
            return redirect(url_for('main.analyze_list'))

        # Verify file belongs to current user
        if file.user_id != current_user.id:
            abort(403)

        # Get related transactions for this file
        transactions = Transaction.query.filter_by(
            user_id=current_user.id,
            file_id=file_id
        ).order_by(Transaction.date.desc()).all()

        if not transactions:
            flash('No transactions found in this file', 'info')

        return render_template('analyze.html', 
                             file=file, 
                             transactions=transactions,
                             ai_available=True)
    except Exception as e:
        logger.error(f"Error in analyze route: {str(e)}")
        flash('Error accessing file for analysis', 'error')
        return redirect(url_for('main.analyze_list'))

@main.route('/analyze_data', methods=['GET', 'POST'])
@login_required
def analyze_data():
    """Analyze transaction data with enhanced error handling"""
    try:
        predictor = PredictiveFeatures()
        if not predictor:
            flash('Prediction service initialization failed', 'error')
            return redirect(url_for('main.analyze_list'))

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

@main.route('/icountant', methods=['GET', 'POST'])
@login_required
def icountant():
    """iCountant Assistant route with enhanced error handling"""
    try:
        # Get user's accounts for transaction processing
        accounts = Account.query.filter_by(user_id=current_user.id).all()

        # Initialize iCountant with user's accounts
        icountant = ICountant(accounts)

        # Get any pending transactions
        pending_transaction = Transaction.query.filter_by(
            user_id=current_user.id,
            status='pending'
        ).first()

        if request.method == 'POST':
            if 'transaction_id' in request.form:
                selected_account = request.form.get('selected_account')
                if selected_account:
                    success, message, completed_transaction = icountant.complete_transaction(int(selected_account))
                    if success:
                        flash('Transaction processed successfully', 'success')
                    else:
                        flash(f'Error processing transaction: {message}', 'error')
                else:
                    flash('Please select an account', 'warning')

        # Get recently processed transactions
        recently_processed = Transaction.query.filter_by(
            user_id=current_user.id,
            status='completed'
        ).order_by(Transaction.date.desc()).limit(5).all()

        return render_template('icountant.html',
                             accounts=accounts,
                             transaction=pending_transaction,
                             recently_processed=recently_processed)

    except Exception as e:
        logger.error(f"Error in iCountant interface: {str(e)}", exc_info=True)
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


@main.route('/settings', methods=['GET', 'POST'])
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