"""
Routes for handling bank statement uploads
Implements secure file handling and validation
Separate from historical data processing
"""
import logging
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from flask_wtf import FlaskForm
from wtforms import FileField, SelectField, SubmitField
from wtforms.validators import DataRequired

from models import db, Account, UploadedFile
from .upload_validator import BankStatementValidator

# Configure logging
logger = logging.getLogger(__name__)
file_handler = logging.FileHandler('bank_statements.log')
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))
logger.addHandler(file_handler)
logger.setLevel(logging.DEBUG)

class BankStatementUploadForm(FlaskForm):
    """Form for bank statement upload with CSRF protection"""
    account = SelectField('Select Bank Account', validators=[DataRequired()],
                         description='Select the bank account this statement belongs to')
    file = FileField('Bank Statement File', validators=[DataRequired()])
    submit = SubmitField('Upload')

    def __init__(self, *args, **kwargs):
        """Initialize form and populate account choices"""
        super(BankStatementUploadForm, self).__init__(*args, **kwargs)
        if current_user.is_authenticated:
            try:
                # Get bank accounts (starting with ca.810)
                bank_accounts = Account.query.filter(
                    Account.user_id == current_user.id,
                    Account.link.like('ca.810%')
                ).all()
                self.account.choices = [(str(acc.id), f"{acc.link} - {acc.name}") for acc in bank_accounts]
                logger.info(f"Found {len(bank_accounts)} bank accounts for user {current_user.id}")
            except Exception as e:
                logger.error(f"Error loading bank accounts: {str(e)}")
                self.account.choices = []

@bank_statements.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """Handle bank statement upload with validation"""
    try:
        form = BankStatementUploadForm()
        logger.info("Processing bank statement upload request")
        
        if request.method == 'POST':
            logger.debug(f"Form validation result: {form.validate()}")
            
            if not form.validate_on_submit():
                logger.error("Form validation failed")
                if request.is_xhr:
                    return jsonify({
                        'success': False,
                        'error': 'Form validation failed'
                    })
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
                        })
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
                        })
                    flash('No file selected', 'error')
                    return redirect(url_for('bank_statements.upload'))

                filename = secure_filename(file.filename)
                
                # Initialize validator
                validator = BankStatementValidator()
                
                # Validate and process file
                if validator.validate_and_process(file, account_id, current_user.id):
                    if request.is_xhr:
                        return jsonify({
                            'success': True,
                            'message': 'Bank statement processed successfully'
                        })
                    flash('Bank statement processed successfully', 'success')
                else:
                    error_messages = validator.get_error_messages()
                    if request.is_xhr:
                        return jsonify({
                            'success': False,
                            'error': error_messages[0] if error_messages else 'Processing failed'
                        })
                    for message in error_messages:
                        flash(message, 'error')
                
                return redirect(url_for('bank_statements.upload'))

            except Exception as e:
                logger.error(f"Error in upload process: {str(e)}")
                if request.is_xhr:
                    return jsonify({
                        'success': False,
                        'error': f'Error in upload process: {str(e)}'
                    })
                flash('Error in upload process: ' + str(e), 'error')
                return redirect(url_for('bank_statements.upload'))

        # GET request - show upload form
        recent_files = (UploadedFile.query
                       .filter_by(user_id=current_user.id)
                       .order_by(UploadedFile.upload_date.desc())
                       .limit(10)
                       .all())

        return render_template('bank_statements/upload.html',
                             form=form,
                             recent_files=recent_files)

    except Exception as e:
        logger.error(f"Error in upload route: {str(e)}", exc_info=True)
        if request.is_xhr:
            return jsonify({
                'success': False,
                'error': 'An unexpected error occurred'
            })
        flash('An error occurred', 'error')
        return redirect(url_for('bank_statements.upload'))
