"""
Routes for handling historical data uploads and processing
Implements comprehensive validation and error reporting
"""
import logging
import pandas as pd
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from decimal import Decimal
from flask_wtf import FlaskForm
from wtforms import FileField, SubmitField, SelectField
from wtforms.validators import DataRequired

from models import db, Account, HistoricalData
from . import historical_data
from .upload_diagnostics import UploadDiagnostics

# Configure logging with detailed format
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
file_handler = logging.FileHandler('upload_debug.log')
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))
logger.addHandler(file_handler)

class UploadForm(FlaskForm):
    """Form for file upload with CSRF protection"""
    account = SelectField('Select Bank Account', validators=[DataRequired()], 
                         description='Select the bank account this statement belongs to')
    file = FileField('Bank Statement File', validators=[DataRequired()])
    submit = SubmitField('Upload')

    def __init__(self, *args, **kwargs):
        """Initialize form and populate account choices"""
        super(UploadForm, self).__init__(*args, **kwargs)
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

@historical_data.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """Handle historical data upload and processing with validation"""
    try:
        form = UploadForm()
        logger.info(f"Processing {request.method} request to /upload")
        logger.debug(f"Request headers: {dict(request.headers)}")
        logger.debug(f"Form data present: {bool(request.form)}")
        logger.debug(f"Files present: {bool(request.files)}")

        if request.method == 'POST':
            if not form.validate_on_submit():
                logger.error("Form validation failed")
                logger.error(f"Form errors: {form.errors}")
                error_messages = []
                for field, errors in form.errors.items():
                    for error in errors:
                        error_messages.append(f"{field}: {error}")

                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'success': False,
                        'error': 'Form validation failed',
                        'details': error_messages
                    }), 400

                for message in error_messages:
                    flash(message, 'error')
                return redirect(url_for('historical_data.upload'))

            try:
                # Get selected bank account
                account_id = int(form.account.data)
                account = Account.query.get(account_id)
                if not account or account.user_id != current_user.id:
                    error_msg = 'Invalid bank account selected'
                    logger.error(error_msg)
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return jsonify({'success': False, 'error': error_msg}), 400
                    flash(error_msg, 'error')
                    return redirect(url_for('historical_data.upload'))

                # Process file upload
                file = form.file.data
                if not file or not file.filename:
                    error_msg = 'No file selected'
                    logger.error(error_msg)
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return jsonify({'success': False, 'error': error_msg}), 400
                    flash(error_msg, 'error')
                    return redirect(url_for('historical_data.upload'))

                filename = secure_filename(file.filename)
                if not filename.lower().endswith(('.csv', '.xlsx')):
                    error_msg = 'Invalid file format. Please upload a CSV or Excel file.'
                    logger.error(f"Invalid file type: {filename}")
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return jsonify({'success': False, 'error': error_msg}), 400
                    flash(error_msg, 'error')
                    return redirect(url_for('historical_data.upload'))

                # Initialize diagnostics
                diagnostics = UploadDiagnostics()

                try:
                    # Read file content
                    if filename.endswith('.xlsx'):
                        df = pd.read_excel(file, engine='openpyxl')
                        logger.info("Successfully read Excel file")
                    else:
                        try:
                            df = pd.read_csv(file, encoding='utf-8')
                            logger.info("Successfully read CSV file with UTF-8 encoding")
                        except UnicodeDecodeError:
                            file.seek(0)
                            df = pd.read_csv(file, encoding='latin1')
                            logger.info("Successfully read CSV file with Latin-1 encoding")

                    logger.debug(f"File contents: Columns={df.columns.tolist()}, Rows={len(df)}")

                    # Validate file structure
                    if not diagnostics.validate_file_structure(df):
                        messages = diagnostics.get_user_friendly_messages()
                        error_msg = messages[0]['message'] if messages else 'File validation failed'
                        logger.error(f"File structure validation failed: {error_msg}")
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return jsonify({'success': False, 'error': error_msg}), 400
                        flash(error_msg, 'error')
                        return redirect(url_for('historical_data.upload'))

                    # Process rows with enhanced error handling
                    success_count = 0
                    error_count = 0
                    errors = []

                    for idx, row in df.iterrows():
                        try:
                            is_valid, cleaned_data = diagnostics.validate_row(row, idx + 2)
                            if is_valid:
                                entry = HistoricalData(
                                    date=cleaned_data['date'],
                                    description=cleaned_data['description'],
                                    amount=cleaned_data['amount'],
                                    explanation=str(row.get('Explanation', '')).strip()[:200],
                                    account_id=account_id,
                                    user_id=current_user.id
                                )
                                db.session.add(entry)
                                success_count += 1

                                # Commit in batches
                                if success_count % 100 == 0:
                                    db.session.commit()
                                    logger.info(f"Committed batch of {success_count} entries")
                        except Exception as e:
                            error_count += 1
                            error_msg = f"Error in row {idx + 2}: {str(e)}"
                            logger.error(error_msg)
                            errors.append(error_msg)

                    # Final commit
                    if success_count > 0:
                        try:
                            db.session.commit()
                            logger.info(f"Successfully processed {success_count} entries")

                            response_data = {
                                'success': True,
                                'message': f'Successfully processed {success_count} entries'
                            }

                            if error_count > 0:
                                response_data['warning'] = f'{error_count} entries had errors'
                                response_data['errors'] = errors[:5]  # First 5 errors

                            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                                return jsonify(response_data)

                            flash(response_data['message'], 'success')
                            if 'warning' in response_data:
                                flash(response_data['warning'], 'warning')

                        except Exception as e:
                            db.session.rollback()
                            error_msg = f"Error committing changes: {str(e)}"
                            logger.error(error_msg)
                            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                                return jsonify({'success': False, 'error': error_msg}), 400
                            flash(error_msg, 'error')

                    return redirect(url_for('historical_data.upload'))

                except Exception as e:
                    error_msg = f"Error processing file: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return jsonify({'success': False, 'error': error_msg}), 400
                    flash(error_msg, 'error')
                    return redirect(url_for('historical_data.upload'))

            except Exception as e:
                error_msg = f"Error in upload process: {str(e)}"
                logger.error(error_msg, exc_info=True)
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'error': error_msg}), 400
                flash(error_msg, 'error')
                return redirect(url_for('historical_data.upload'))

        # GET request - show upload form
        historical_entries = (HistoricalData.query
                          .filter_by(user_id=current_user.id)
                          .order_by(HistoricalData.date.desc())
                          .limit(10)
                          .all())

        return render_template('historical_data/upload.html',
                             form=form,
                             entries=historical_entries)

    except Exception as e:
        error_msg = f"Unexpected error in upload route: {str(e)}"
        logger.error(error_msg, exc_info=True)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': error_msg}), 400
        flash('An unexpected error occurred', 'error')
        return redirect(url_for('historical_data.upload'))