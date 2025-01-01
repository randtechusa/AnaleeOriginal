"""
Routes for handling bank statement uploads
Implements secure file handling and validation
Separate from historical data processing
Enhanced with user-friendly error notifications
"""
import logging
import os
from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os

from . import bank_statements
from .forms import BankStatementUploadForm
from .services import BankStatementService
from .models import BankStatementUpload
from models import Account

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

            # Log debugging information
            logger.debug(f"Form validation result: {form.validate()}")
            logger.debug(f"Form errors: {form.errors}")
            logger.debug(f"Request files: {request.files}")
            logger.debug(f"Form data: {request.form}")
            logger.debug(f"Is AJAX request: {is_ajax}")

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

                # Process file upload with enhanced validation
                file = form.file.data
                if not file or not file.filename:
                    logger.error("No file selected")
                    if is_ajax:
                        return jsonify({
                            'success': False,
                            'error': 'Please select a file to upload'
                        }), 400
                    flash('Please select a file to upload.', 'error')
                    return redirect(url_for('bank_statements.upload'))

                # Validate file extension
                filename = secure_filename(file.filename)
                file_ext = os.path.splitext(filename)[1].lower()
                if file_ext not in ['.csv', '.xlsx']:
                    if is_ajax:
                        return jsonify({
                            'success': False,
                            'error': 'Please upload only Excel (.xlsx) or CSV (.csv) files.'
                        }), 400
                    flash('Please upload only Excel (.xlsx) or CSV (.csv) files.', 'error')
                    return redirect(url_for('bank_statements.upload'))

                # Ensure upload directory exists
                upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
                if not os.path.exists(upload_folder):
                    os.makedirs(upload_folder)

                logger.info(f"Processing file: {filename}")

                # Process upload using service with enhanced error handling
                service = BankStatementService()
                success, response = service.process_upload(
                    file=file,
                    account_id=account_id,
                    user_id=current_user.id
                )

                if success:
                    if is_ajax:
                        return jsonify({
                            'success': True,
                            'message': 'Bank statement processed successfully!',
                            'rows_processed': response.get('rows_processed', 0),
                            'processing_notes': response.get('processing_notes', [])
                        })
                    flash('Bank statement processed successfully! ' + 
                          response.get('message', ''), 'success')

                    # Add processing notes if available
                    if response.get('processing_notes'):
                        for note in response['processing_notes']:
                            flash(note, 'info')
                else:
                    # Display main error message
                    if is_ajax:
                        return jsonify({
                            'success': False,
                            'error': response.get('error', 'Processing failed'),
                            'details': response.get('details', [])
                        }), 400
                    flash(response.get('error', 'Processing failed'), 'error')

                    # Display detailed errors if available
                    if response.get('details'):
                        for detail in response['details']:
                            flash(f"Detail: {detail}", 'warning')

                return redirect(url_for('bank_statements.upload'))

            except Exception as e:
                logger.error(f"Error in upload process: {str(e)}", exc_info=True)
                if is_ajax:
                    return jsonify({
                        'success': False,
                        'error': 'An error occurred during upload',
                        'details': [str(e)]
                    }), 500
                flash('An error occurred during upload. Please try again or contact support if the issue persists.', 'error')
                return redirect(url_for('bank_statements.upload'))

        # GET request - show upload form with enhanced bank account validation
        try:
            # Get user's bank accounts that start with ca.810
            bank_accounts = Account.query.filter(
                Account.user_id == current_user.id,
                Account.number.startswith('ca.810')  # Updated to use number field
            ).all()

            if not bank_accounts:
                flash('No valid bank accounts found. Please create a bank account (starting with ca.810) in the settings first.', 'warning')

            logger.info(f"Found {len(bank_accounts)} bank accounts for user {current_user.id}")

            # Get recent uploads with status information
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
            logger.error(f"Error retrieving bank accounts: {str(e)}", exc_info=True)
            flash('Error loading bank accounts. Please try again or contact support.', 'error')
            return redirect(url_for('bank_statements.upload'))

    except Exception as e:
        logger.error(f"Error in upload route: {str(e)}", exc_info=True)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'error': 'An unexpected error occurred',
                'details': [str(e)]
            }), 500
        flash('An unexpected error occurred. Please try again or contact support.', 'error')
        return redirect(url_for('bank_statements.upload'))