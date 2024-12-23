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
        super(UploadForm, self).__init__(*args, **kwargs)
        if current_user.is_authenticated:
            # Get bank accounts (starting with ca.810)
            bank_accounts = Account.query.filter(
                Account.user_id == current_user.id,
                Account.link.like('ca.810%')
            ).all()
            self.account.choices = [(str(acc.id), f"{acc.link} - {acc.name}") for acc in bank_accounts]

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

@historical_data.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """Handle historical data upload and management."""
    try:
        # Initialize form with CSRF protection
        form = UploadForm()

        if request.method == 'POST':
            logger.info("Processing upload request")

            # Validate form submission
            if not form.validate_on_submit():
                logger.error("Form validation failed")
                for field, errors in form.errors.items():
                    for error in errors:
                        flash(f"{field}: {error}", 'error')
                return redirect(url_for('historical_data.upload'))

            # Get selected bank account
            try:
                account_id = int(form.account.data)
                account = Account.query.get(account_id)
                if not account or account.user_id != current_user.id:
                    flash('Invalid bank account selected', 'error')
                    return redirect(url_for('historical_data.upload'))
            except (ValueError, TypeError):
                flash('Invalid bank account selection', 'error')
                return redirect(url_for('historical_data.upload'))

            # Process file upload
            file = form.file.data
            if not file or not file.filename:
                flash('No file selected', 'error')
                return redirect(url_for('historical_data.upload'))

            if not validate_file_type(file.filename):
                flash('Invalid file format. Please upload a CSV or Excel file.', 'error')
                return redirect(url_for('historical_data.upload'))

            try:
                # Read file based on type
                if file.filename.endswith('.xlsx'):
                    df = pd.read_excel(file, engine='openpyxl')
                else:
                    try:
                        df = pd.read_csv(file, encoding='utf-8')
                    except UnicodeDecodeError:
                        file.seek(0)
                        df = pd.read_csv(file, encoding='latin1')

                # Process each row
                success_count = 0
                error_count = 0

                for _, row in df.iterrows():
                    try:
                        # Validate and clean data
                        date = validate_date(row.get('Date'))
                        amount = validate_amount(row.get('Amount'))
                        description = sanitize_text(row.get('Description', ''))
                        explanation = sanitize_text(row.get('Explanation', ''))

                        if not all([date, amount is not None, description]):
                            error_count += 1
                            continue

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

                if error_count > 0:
                    flash(f'{error_count} entries had errors. Check logs for details.', 'warning')

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

def preview_data_frame(df):
    """Preview and validate the uploaded data without saving."""
    preview_results = {
        'valid_rows': [],
        'invalid_rows': [],
        'warnings': [],
        'total_rows': len(df),
        'columns_found': list(df.columns),
        'sample_data': []
    }

    # Check required columns
    required_columns = ['Date', 'Description', 'Amount', 'Explanation', 'Account']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        preview_results['invalid_rows'].append({
            'row': 0,
            'error': f"Missing required columns: {', '.join(missing_columns)}"
        })
        return preview_results

    # Validate each row
    for idx, row in df.iterrows():
        row_num = idx + 2  # Add 2 because idx starts at 0 and we skip header row
        row_issues = []
        row_warnings = []

        # Validate each field
        date = validate_date(row['Date'])
        if not date:
            row_issues.append("Invalid date format")

        if not row['Description'] or not isinstance(row['Description'], str):
            row_issues.append("Invalid or empty description")
        elif len(str(row['Description'])) > 200:
            row_warnings.append("Description will be truncated to 200 characters")

        amount = validate_amount(row['Amount'])
        if amount is None:
            row_issues.append("Invalid amount value")

        # Collect row data for preview
        row_data = {
            'row_number': row_num,
            'date': str(row['Date']),
            'description': str(row['Description'])[:200],
            'amount': str(row['Amount']),
            'explanation': str(row.get('Explanation', ''))[:200],
            'account': str(row.get('Account', '')),
            'is_valid': len(row_issues) == 0
        }

        if row_issues:
            preview_results['invalid_rows'].append({
                'row': row_num,
                'data': row_data,
                'errors': row_issues
            })
        else:
            preview_results['valid_rows'].append(row_data)

        if row_warnings:
            preview_results['warnings'].append({
                'row': row_num,
                'warnings': row_warnings
            })

        # Add to sample data (first 5 rows)
        if idx < 5:
            preview_results['sample_data'].append(row_data)

    return preview_results

@historical_data.route('/preview', methods=['POST'])
@login_required
def preview_upload():
    """Preview uploaded file data without importing."""
    try:
        if 'file' not in request.files:
            logger.error("No file part in request")
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['file']
        if not file.filename:
            logger.error("No selected file")
            return jsonify({'error': 'No file selected'}), 400

        if not validate_file_type(file.filename):
            logger.error(f"Invalid file type: {file.filename}")
            return jsonify({'error': 'Invalid file format. Please upload a CSV or Excel file.'}), 400

        try:
            # Read the file with explicit encoding for CSV
            if file.filename.endswith('.xlsx'):
                logger.info(f"Reading Excel file: {file.filename}")
                df = pd.read_excel(file, engine='openpyxl')
            else:
                logger.info(f"Reading CSV file: {file.filename}")
                # Try different encodings
                try:
                    df = pd.read_csv(file, encoding='utf-8')
                except UnicodeDecodeError:
                    file.seek(0)  # Reset file pointer
                    df = pd.read_csv(file, encoding='latin1')

            # Get preview results
            logger.info("Generating preview results")
            preview_results = preview_data_frame(df)

            # Add summary statistics
            preview_results['summary'] = {
                'total_rows': len(df),
                'valid_rows': len(preview_results['valid_rows']),
                'invalid_rows': len(preview_results['invalid_rows']),
                'warnings': len(preview_results['warnings'])
            }

            logger.info("Preview generated successfully")
            return jsonify(preview_results)

        except Exception as e:
            logger.error(f"Error processing file for preview: {str(e)}", exc_info=True)
            return jsonify({'error': f'Error processing file: {str(e)}'}), 500

    except Exception as e:
        logger.error(f"Error in preview route: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500