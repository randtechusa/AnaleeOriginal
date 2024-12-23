"""
Routes for handling historical data uploads and processing
Implements real-time progress updates and comprehensive error reporting
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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

        if request.method == 'POST':
            logger.info("Received POST request")

            if not form.validate_on_submit():
                logger.error("Form validation failed")
                if request.is_xhr:
                    return jsonify({
                        'success': False,
                        'error': 'Form validation failed. Please ensure all fields are filled correctly.'
                    })
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
                        })
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
                        })
                    flash('No file selected', 'error')
                    return redirect(url_for('historical_data.upload'))

                filename = secure_filename(file.filename)
                if not filename.lower().endswith(('.csv', '.xlsx')):
                    logger.error(f"Invalid file type: {filename}")
                    if request.is_xhr:
                        return jsonify({
                            'success': False,
                            'error': 'Invalid file format. Please upload a CSV or Excel file.'
                        })
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

                    # Validate file structure
                    if not diagnostics.validate_file_structure(df):
                        logger.error("File structure validation failed")
                        messages = diagnostics.get_user_friendly_messages()
                        if request.is_xhr:
                            return jsonify({
                                'success': False,
                                'error': messages[0]['message'] if messages else 'File validation failed'
                            })
                        for message in messages:
                            flash(message['message'], message['type'])
                        return redirect(url_for('historical_data.upload'))

                    # Process rows
                    success_count = 0
                    error_count = 0
                    total_rows = len(df)

                    for idx, row in df.iterrows():
                        row_num = idx + 2  # Add 2 for header row and 0-based index
                        is_valid, cleaned_data = diagnostics.validate_row(row, row_num)

                        if is_valid:
                            try:
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

                            except Exception as e:
                                logger.error(f"Error saving row {row_num}: {str(e)}")
                                error_count += 1

                    # Final commit for remaining entries
                    if success_count > 0:
                        db.session.commit()
                        logger.info(f"Successfully processed {success_count} entries")
                        if request.is_xhr:
                            return jsonify({
                                'success': True,
                                'message': f'Successfully processed {success_count} entries.'
                            })
                        flash(f'Successfully processed {success_count} entries.', 'success')

                    if error_count > 0:
                        flash(f'{error_count} entries had errors. Check the error log for details.', 'warning')

                    # Display validation messages
                    messages = diagnostics.get_user_friendly_messages()
                    if request.is_xhr:
                        return jsonify({
                            'success': True,
                            'messages': messages
                        })
                    for message in messages:
                        flash(message['message'], message['type'])

                    return redirect(url_for('historical_data.upload'))

                except Exception as e:
                    logger.error(f"Error processing file: {str(e)}")
                    db.session.rollback()
                    if request.is_xhr:
                        return jsonify({
                            'success': False,
                            'error': f'Error processing file: {str(e)}'
                        })
                    flash('Error processing file: ' + str(e), 'error')
                    return redirect(url_for('historical_data.upload'))

            except Exception as e:
                logger.error(f"Error in upload process: {str(e)}")
                if request.is_xhr:
                    return jsonify({
                        'success': False,
                        'error': f'Error in upload process: {str(e)}'
                    })
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
        logger.error(f"Error in upload route: {str(e)}")
        if request.is_xhr:
            return jsonify({
                'success': False,
                'error': 'An unexpected error occurred'
            })
        flash('An error occurred', 'error')
        return redirect(url_for('historical_data.upload'))