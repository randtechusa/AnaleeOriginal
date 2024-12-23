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
        logger.info("Processing upload request")
        logger.debug(f"Request method: {request.method}")
        logger.debug(f"Form data: {request.form}")
        logger.debug(f"Files: {request.files}")

        # Handle AJAX request for checking CSRF token
        if request.is_xhr and request.method == 'GET':
            return jsonify({
                'csrf_token': form.csrf_token._value()
            })

        if request.method == 'POST':
            logger.info("Received POST request")
            logger.debug(f"CSRF token present: {'csrf_token' in request.form}")
            logger.debug(f"Form validation result: {form.validate()}")
            logger.debug(f"Form errors: {form.errors}")

            # Fix for AJAX upload with proper CSRF validation
            if request.is_xhr:
                if 'csrf_token' not in request.form:
                    logger.error("CSRF token missing in AJAX request")
                    return jsonify({
                        'success': False,
                        'error': 'CSRF token missing'
                    }), 400

            if not form.validate_on_submit():
                logger.error("Form validation failed")
                logger.error(f"Form errors: {form.errors}")
                if request.is_xhr:
                    return jsonify({
                        'success': False,
                        'error': 'Form validation failed. Please ensure all fields are filled correctly.',
                        'errors': form.errors
                    }), 400
                for field, errors in form.errors.items():
                    for error in errors:
                        flash(f"{field}: {error}", 'error')
                return redirect(url_for('historical_data.upload'))

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
                    return redirect(url_for('historical_data.upload'))

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
                    return redirect(url_for('historical_data.upload'))

                filename = secure_filename(file.filename)
                if not filename.lower().endswith(('.csv', '.xlsx')):
                    logger.error(f"Invalid file type: {filename}")
                    if request.is_xhr:
                        return jsonify({
                            'success': False,
                            'error': 'Invalid file format. Please upload a CSV or Excel file.'
                        }), 400
                    flash('Invalid file format. Please upload a CSV or Excel file.', 'error')
                    return redirect(url_for('historical_data.upload'))

                # Initialize diagnostics
                diagnostics = UploadDiagnostics()

                # Read and validate file
                try:
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

                    # Log data validation before processing
                    logger.debug(f"Data columns: {df.columns.tolist()}")
                    logger.debug(f"Data shape: {df.shape}")

                    # Validate file structure
                    if not diagnostics.validate_file_structure(df):
                        logger.error("File structure validation failed")
                        messages = diagnostics.get_user_friendly_messages()
                        if request.is_xhr:
                            return jsonify({
                                'success': False,
                                'error': messages[0]['message'] if messages else 'File validation failed'
                            }), 400
                        for message in messages:
                            flash(message['message'], message['type'])
                        return redirect(url_for('historical_data.upload'))

                    # Process rows with enhanced error handling
                    success_count = 0
                    error_count = 0
                    total_rows = len(df)
                    errors = []

                    for idx, row in df.iterrows():
                        row_num = idx + 2  # Add 2 for header row and 0-based index
                        try:
                            is_valid, cleaned_data = diagnostics.validate_row(row, row_num)

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

                                # Commit every 100 rows to prevent memory issues
                                if success_count % 100 == 0:
                                    db.session.commit()
                                    logger.info(f"Committed {success_count} entries")

                        except Exception as row_error:
                            error_count += 1
                            error_msg = f"Error processing row {row_num}: {str(row_error)}"
                            logger.error(error_msg)
                            errors.append(error_msg)

                    # Final commit for remaining entries
                    if success_count > 0:
                        db.session.commit()
                        logger.info(f"Successfully processed {success_count} entries")
                        if request.is_xhr:
                            return jsonify({
                                'success': True,
                                'message': f'Successfully processed {success_count} entries.',
                                'errors': errors if errors else None
                            })
                        flash(f'Successfully processed {success_count} entries.', 'success')

                    if error_count > 0:
                        message = f'{error_count} entries had errors. Check the error log for details.'
                        logger.warning(message)
                        if request.is_xhr:
                            return jsonify({
                                'success': True,
                                'warning': message,
                                'errors': errors
                            })
                        flash(message, 'warning')

                    return redirect(url_for('historical_data.upload'))

                except Exception as e:
                    logger.error(f"Error processing file: {str(e)}", exc_info=True)
                    db.session.rollback()
                    if request.is_xhr:
                        return jsonify({
                            'success': False,
                            'error': f'Error processing file: {str(e)}'
                        }), 400
                    flash('Error processing file: ' + str(e), 'error')
                    return redirect(url_for('historical_data.upload'))

            except Exception as e:
                logger.error(f"Error in upload process: {str(e)}", exc_info=True)
                if request.is_xhr:
                    return jsonify({
                        'success': False,
                        'error': f'Error in upload process: {str(e)}'
                    }), 400
                flash('Error in upload process: ' + str(e), 'error')
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
        logger.error(f"Error in upload route: {str(e)}", exc_info=True)
        if request.is_xhr:
            return jsonify({
                'success': False,
                'error': 'An unexpected error occurred'
            }), 400
        flash('An error occurred', 'error')
        return redirect(url_for('historical_data.upload'))