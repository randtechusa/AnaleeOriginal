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

@historical_data.route('/')
@historical_data.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """Handle historical data upload and processing with validation"""
    try:
        logger.info("Processing historical data upload request")
        form = UploadForm()

        if request.method == 'POST':
            if not form.validate_on_submit():
                logger.error(f"Form validation failed: {form.errors}")
                for field, errors in form.errors.items():
                    for error in errors:
                        flash(f"{field}: {error}", 'error')
                return redirect(url_for('historical_data.upload'))

            try:
                account_id = int(form.account.data)
                account = Account.query.get(account_id)

                if not account or account.user_id != current_user.id:
                    logger.error(f"Invalid account selected: {account_id}")
                    flash('Invalid bank account selected', 'error')
                    return redirect(url_for('historical_data.upload'))

                file = form.file.data
                if not file:
                    flash('No file selected', 'error')
                    return redirect(url_for('historical_data.upload'))

                filename = secure_filename(file.filename)
                if not filename.lower().endswith(('.csv', '.xlsx')):
                    flash('Invalid file format. Please upload a CSV or Excel file.', 'error')
                    return redirect(url_for('historical_data.upload'))

                # Initialize upload diagnostics
                diagnostics = UploadDiagnostics()

                try:
                    # Read file based on extension
                    if filename.endswith('.xlsx'):
                        df = pd.read_excel(file, engine='openpyxl')
                    else:
                        try:
                            df = pd.read_csv(file, encoding='utf-8')
                        except UnicodeDecodeError:
                            df = pd.read_csv(file, encoding='latin1')

                    # Validate file structure
                    if not diagnostics.validate_file_structure(df):
                        messages = diagnostics.get_user_friendly_messages()
                        for message in messages:
                            flash(message['message'], message['type'])
                        return redirect(url_for('historical_data.upload'))

                    # Process rows with enhanced error handling
                    success_count = 0
                    error_count = 0

                    for idx, row in df.iterrows():
                        is_valid, cleaned_data = diagnostics.validate_row(row, idx + 2)
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

                                if success_count % 100 == 0:
                                    db.session.commit()
                            except Exception as e:
                                logger.error(f"Error saving row {idx + 2}: {str(e)}")
                                error_count += 1

                    if success_count > 0:
                        db.session.commit()
                        flash(f'Successfully processed {success_count} entries.', 'success')

                    if error_count > 0:
                        flash(f'{error_count} entries had errors. Check the error log for details.', 'warning')

                    return redirect(url_for('historical_data.upload'))

                except Exception as e:
                    logger.error(f"Error processing file: {str(e)}")
                    db.session.rollback()
                    flash(f'Error processing file: {str(e)}', 'error')
                    return redirect(url_for('historical_data.upload'))

            except Exception as e:
                logger.error(f"Error in upload process: {str(e)}")
                flash(f'Error in upload process: {str(e)}', 'error')
                return redirect(url_for('historical_data.upload'))

        # GET request - show upload form with recent entries
        historical_entries = (HistoricalData.query
                            .filter_by(user_id=current_user.id)
                            .order_by(HistoricalData.date.desc())
                            .limit(10)
                            .all())

        logger.info("Rendering historical data upload template")
        return render_template('historical_data/upload.html', #Corrected the template name here
                             form=form,
                             entries=historical_entries)

    except Exception as e:
        logger.error(f"Error in upload route: {str(e)}", exc_info=True)
        flash('An unexpected error occurred', 'error')
        return redirect(url_for('historical_data.upload'))