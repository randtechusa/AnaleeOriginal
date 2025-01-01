"""
Routes for handling bank statement uploads
Implements secure file handling and validation
"""
import logging
import os
from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from werkzeug.utils import secure_filename
from flask_login import login_required, current_user

from . import bank_statements
from .forms import BankStatementUploadForm
from .services import BankStatementService
from models import Account, BankStatementUpload, db

# Configure logging
logger = logging.getLogger(__name__)

@bank_statements.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """Handle bank statement upload with enhanced validation and error handling"""
    try:
        form = BankStatementUploadForm()
        logger.info("Processing bank statement upload request")

        if request.method == 'POST':
            # Check if it's an AJAX request
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

            if not form.validate_on_submit():
                logger.error(f"Form validation failed: {form.errors}")
                error_messages = []
                for field, errors in form.errors.items():
                    error_messages.extend(errors)
                if is_ajax:
                    return jsonify({
                        'success': False,
                        'error': 'Validation failed',
                        'details': error_messages
                    }), 400
                flash('Please ensure all fields are filled correctly: ' + '; '.join(error_messages), 'error')
                return redirect(url_for('bank_statements.upload'))

            try:
                # Get selected bank account with enhanced validation
                account_id = int(form.account.data)
                account = Account.query.get(account_id)
                if not account or account.user_id != current_user.id:
                    logger.error(f"Invalid account selected: {account_id}")
                    if is_ajax:
                        return jsonify({
                            'success': False,
                            'error': 'Invalid bank account selected'
                        }), 400
                    flash('Invalid bank account selected. Please choose a valid account.', 'error')
                    return redirect(url_for('bank_statements.upload'))

                # Process file upload
                file = form.file.data
                if not file:
                    if is_ajax:
                        return jsonify({
                            'success': False,
                            'error': 'Please select a file to upload'
                        }), 400
                    flash('Please select a file to upload.', 'error')
                    return redirect(url_for('bank_statements.upload'))

                # Process upload using service
                service = BankStatementService()
                success, response = service.process_upload(
                    file=file,
                    account_id=account_id,
                    user_id=current_user.id
                )

                if success:
                    if is_ajax:
                        return jsonify(response)
                    flash('Bank statement processed successfully!', 'success')
                else:
                    if is_ajax:
                        return jsonify(response), 400
                    flash(response.get('error', 'Processing failed'), 'error')

                return redirect(url_for('bank_statements.upload'))

            except Exception as e:
                logger.error(f"Error processing upload: {str(e)}", exc_info=True)
                if is_ajax:
                    return jsonify({
                        'success': False,
                        'error': 'An error occurred during upload',
                        'details': [str(e)]
                    }), 500
                flash('An error occurred during upload. Please try again.', 'error')
                return redirect(url_for('bank_statements.upload'))

        # Get user's bank accounts
        bank_accounts = Account.query.filter(
            Account.user_id == current_user.id,
            Account.link.like('ca.810%')
        ).all()

        if not bank_accounts:
            flash('No bank accounts found. Please create a bank account first.', 'warning')

        # Get recent uploads
        recent_files = BankStatementUpload.query.filter_by(
            user_id=current_user.id
        ).order_by(BankStatementUpload.upload_date.desc()).limit(10).all()

        return render_template('bank_statements/upload.html',
                           form=form,
                           bank_accounts=bank_accounts,
                           recent_files=recent_files)

    except Exception as e:
        logger.error(f"Error in upload route: {str(e)}", exc_info=True)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'error': 'An unexpected error occurred',
                'details': [str(e)]
            }), 500
        flash('An unexpected error occurred. Please try again.', 'error')
        return redirect(url_for('bank_statements.upload'))