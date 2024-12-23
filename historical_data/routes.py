"""Routes for handling historical data uploads and processing"""
import logging
import pandas as pd
from datetime import datetime
from flask import request, render_template, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import re
from decimal import Decimal, InvalidOperation
from flask_wtf import FlaskForm
from wtforms import FileField, SubmitField, SelectField
from wtforms.validators import DataRequired

from models import db, Account, HistoricalData
from . import historical_data
from .ai_suggestions import HistoricalDataAI

# Configure logging
logger = logging.getLogger(__name__)

# Define upload form with CSRF protection
class UploadForm(FlaskForm):
    """Form for file upload with CSRF protection"""
    account = SelectField('Select Bank Account', validators=[DataRequired()], 
                         description='Select the bank account this statement belongs to (Accounts starting with ca.810)')
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

def validate_upload_data(df):
    """Validate the uploaded data structure and content"""
    required_columns = ['Date', 'Description', 'Amount']
    errors = []

    # Check if DataFrame is empty
    if df.empty:
        return ['The uploaded file is empty']

    # Verify required columns exist
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        return [f"Missing required columns: {', '.join(missing_columns)}"]

    # Basic data validation
    for idx, row in df.iterrows():
        row_num = idx + 2  # Add 2 for header row and 0-based index
        try:
            # Date validation
            if pd.isna(row['Date']):
                errors.append(f"Row {row_num}: Missing date")
            else:
                try:
                    pd.to_datetime(row['Date'])
                except Exception:
                    errors.append(f"Row {row_num}: Invalid date format")

            # Amount validation
            if pd.isna(row['Amount']):
                errors.append(f"Row {row_num}: Missing amount")
            else:
                try:
                    Decimal(str(row['Amount']))
                except InvalidOperation:
                    errors.append(f"Row {row_num}: Invalid amount format")

            # Description validation
            if pd.isna(row['Description']) or str(row['Description']).strip() == '':
                errors.append(f"Row {row_num}: Missing description")

        except Exception as e:
            errors.append(f"Row {row_num}: Error validating data - {str(e)}")

    return errors

@historical_data.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """Handle historical data upload and management."""
    try:
        # Initialize form with CSRF protection
        form = UploadForm()
        logger.info("Processing upload request")

        if request.method == 'POST':
            logger.info("Received POST request")

            # Log form data for debugging
            logger.debug(f"Form data: account={form.account.data}, file={form.file.data.filename if form.file.data else None}")
            logger.debug(f"CSRF Token present: {form.csrf_token.current_token is not None}")

            # Validate form submission
            if not form.validate_on_submit():
                logger.error("Form validation failed")
                for field, errors in form.errors.items():
                    for error in errors:
                        logger.error(f"Form error - {field}: {error}")
                        flash(f"{field}: {error}", 'error')
                return redirect(url_for('historical_data.upload'))

            # Get selected bank account
            try:
                account_id = int(form.account.data)
                account = Account.query.get(account_id)
                if not account or account.user_id != current_user.id:
                    logger.error(f"Invalid account selected: {account_id}")
                    flash('Invalid bank account selected', 'error')
                    return redirect(url_for('historical_data.upload'))
            except (ValueError, TypeError) as e:
                logger.error(f"Error processing account selection: {str(e)}")
                flash('Invalid bank account selection', 'error')
                return redirect(url_for('historical_data.upload'))

            # Process file upload
            file = form.file.data
            if not file or not file.filename:
                logger.error("No file selected")
                flash('No file selected', 'error')
                return redirect(url_for('historical_data.upload'))

            filename = secure_filename(file.filename)
            logger.info(f"Processing file: {filename}")

            if not filename.lower().endswith(('.csv', '.xlsx')):
                logger.error(f"Invalid file type: {filename}")
                flash('Invalid file format. Please upload a CSV or Excel file.', 'error')
                return redirect(url_for('historical_data.upload'))

            try:
                # Read file based on type
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

                # Validate uploaded data
                validation_errors = validate_upload_data(df)
                if validation_errors:
                    for error in validation_errors[:5]:  # Show first 5 errors
                        flash(error, 'error')
                    logger.error(f"Validation errors in upload: {validation_errors}")
                    return redirect(url_for('historical_data.upload'))

                # Process each row
                success_count = 0
                error_count = 0

                for _, row in df.iterrows():
                    try:
                        # Validate and clean data
                        date = pd.to_datetime(row['Date']).date()
                        amount = Decimal(str(row['Amount']))
                        description = str(row['Description']).strip()[:200]
                        explanation = str(row.get('Explanation', '')).strip()[:200]

                        # Create historical data entry
                        entry = HistoricalData(
                            date=date,
                            description=description,
                            amount=amount,
                            explanation=explanation,
                            account_id=account_id,
                            user_id=current_user.id
                        )
                        db.session.add(entry)
                        success_count += 1

                    except Exception as row_error:
                        logger.error(f"Error processing row: {str(row_error)}")
                        error_count += 1
                        continue

                if success_count > 0:
                    db.session.commit()
                    flash(f'Successfully processed {success_count} entries.', 'success')
                    logger.info(f"Successfully processed {success_count} entries")

                if error_count > 0:
                    flash(f'{error_count} entries had errors. Check logs for details.', 'warning')
                    logger.warning(f"{error_count} entries had errors")

                return redirect(url_for('historical_data.upload'))

            except Exception as e:
                logger.error(f"Error processing file: {str(e)}")
                db.session.rollback()
                flash('Error processing file: ' + str(e), 'error')
                return redirect(url_for('historical_data.upload'))

        # GET request - show upload form and existing data
        historical_entries = (HistoricalData.query
                            .filter_by(user_id=current_user.id)
                            .order_by(HistoricalData.date.desc())
                            .limit(100)
                            .all())

        return render_template(
            'historical_data/upload.html',
            form=form,
            entries=historical_entries
        )

    except Exception as e:
        logger.error(f"Error in upload route: {str(e)}")
        flash('An error occurred', 'error')
        return redirect(url_for('historical_data.upload'))

def validate_file_type(filename):
    """Validate if the uploaded file is CSV or Excel."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'csv', 'xlsx'}

def validate_date(date_str):
    """Validate and parse date string."""
    try:
        return pd.to_datetime(date_str).date()
    except Exception:
        return None

def validate_amount(amount_str):
    """Validate and convert amount string to Decimal."""
    try:
        # Remove any currency symbols and whitespace
        cleaned = re.sub(r'[^\d.-]', '', str(amount_str))
        amount = Decimal(cleaned)
        if -1000000000 <= amount <= 1000000000:  # Reasonable limits
            return amount
        return None
    except (InvalidOperation, TypeError):
        return None

def sanitize_text(text, max_length=200):
    """Sanitize and truncate text input."""
    if not isinstance(text, str):
        text = str(text)
    # Remove any special characters except basic punctuation
    text = re.sub(r'[^\w\s.,;:!?()-]', '', text)
    return text.strip()[:max_length]