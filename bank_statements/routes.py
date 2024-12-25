"""
Routes for handling bank statement uploads
Implements secure file handling and validation
Separate from historical data processing
"""
import logging
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from . import bank_statements
from .forms import BankStatementUploadForm
from .services import BankStatementService
from models import Account, BankStatementUpload  # Updated import from main models.py

# Configure logging
logger = logging.getLogger(__name__)

@bank_statements.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """Handle bank statement upload with validation"""
    try:
        form = BankStatementUploadForm()
        logger.info("Processing bank statement upload request")

        if request.method == 'POST':
            # Log debugging information
            logger.debug(f"Form validation result: {form.validate()}")
            logger.debug(f"Form errors: {form.errors}")
            logger.debug(f"Request files: {request.files}")
            logger.debug(f"Form data: {request.form}")

            if not form.validate_on_submit():
                logger.error("Form validation failed")
                if request.is_xhr:
                    return jsonify({
                        'success': False,
                        'error': 'Form validation failed',
                        'errors': form.errors
                    }), 400
                flash('Please ensure all fields are filled correctly.', 'error')
                return redirect(url_for('bank_statements.upload'))

            try:
                # Get selected bank account
                account_id = int(form.account.data)
                account = Account.query.get(account_id)
                if not account or account.user_id != current_user.id:
                    logger.error(f"Invalid account selected: {account_id}")
                    if request.is_xhr:
                        return jsonify({
                            'success': False,
                            'error': 'Invalid bank account selected'
                        }), 400
                    flash('Invalid bank account selected', 'error')
                    return redirect(url_for('bank_statements.upload'))

                # Process file upload
                file = form.file.data
                if not file or not file.filename:
                    logger.error("No file selected")
                    if request.is_xhr:
                        return jsonify({
                            'success': False,
                            'error': 'Please select a file to upload'
                        }), 400
                    flash('No file selected', 'error')
                    return redirect(url_for('bank_statements.upload'))

                # Secure the filename
                filename = secure_filename(file.filename)
                logger.info(f"Processing file: {filename}")

                # Process upload using service
                service = BankStatementService()
                success, response = service.process_upload(
                    file=file,
                    account_id=account_id,
                    user_id=current_user.id
                )

                if request.is_xhr:
                    return jsonify(response)

                if success:
                    flash('Bank statement processed successfully', 'success')
                else:
                    flash(response.get('error', 'Processing failed'), 'error')

                return redirect(url_for('bank_statements.upload'))

            except Exception as e:
                logger.error(f"Error in upload process: {str(e)}")
                if request.is_xhr:
                    return jsonify({
                        'success': False,
                        'error': f'Error in upload process: {str(e)}'
                    }), 500
                flash('Error in upload process: ' + str(e), 'error')
                return redirect(url_for('bank_statements.upload'))

        # GET request - show upload form
        # Get user's bank accounts that start with ca.810
        bank_accounts = Account.query.filter(
            Account.user_id == current_user.id,
            Account.link.startswith('ca.810')
        ).all()
        logger.info(f"Found {len(bank_accounts)} bank accounts for user {current_user.id}")

        recent_files = (BankStatementUpload.query
                       .filter_by(user_id=current_user.id)
                       .order_by(BankStatementUpload.upload_date.desc())
                       .limit(10)
                       .all())

        return render_template('bank_statements/upload.html',
                             form=form,
                             bank_accounts=bank_accounts,
                             recent_files=recent_files)

    except Exception as e:
        logger.error(f"Error in upload route: {str(e)}", exc_info=True)
        if request.is_xhr:
            return jsonify({
                'success': False,
                'error': 'An unexpected error occurred'
            }), 500
        flash('An error occurred', 'error')
        return redirect(url_for('bank_statements.upload'))