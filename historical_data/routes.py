import logging
import pandas as pd
from datetime import datetime
from flask import request, render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import re
from decimal import Decimal, InvalidOperation

from models import db, Account, HistoricalData
from . import historical_data
from .ai_suggestions import HistoricalDataAI

logger = logging.getLogger(__name__)

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

def validate_data_frame(df):
    """Validate the structure and content of the uploaded data."""
    errors = []
    warnings = []
    valid_rows = []  # Initialize valid_rows even when returning early

    # Check required columns
    required_columns = ['Date', 'Description', 'Amount', 'Explanation', 'Account']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        errors.append(f"Missing required columns: {', '.join(missing_columns)}")
        return errors, warnings, valid_rows  # Return all three values consistently

    # Validate each row
    for idx, row in df.iterrows():
        row_num = idx + 2  # Add 2 because idx starts at 0 and we skip header row
        row_errors = []

        # Date validation
        date = validate_date(row['Date'])
        if not date:
            row_errors.append(f"Invalid date format")

        # Description validation
        if not row['Description'] or not isinstance(row['Description'], str):
            row_errors.append(f"Invalid or empty description")
        elif len(str(row['Description'])) > 200:
            warnings.append(f"Row {row_num}: Description will be truncated to 200 characters")

        # Amount validation
        amount = validate_amount(row['Amount'])
        if amount is None:
            row_errors.append(f"Invalid amount value")

        # Explanation validation
        if not row['Explanation'] or not isinstance(row['Explanation'], str):
            row_errors.append(f"Invalid or empty explanation")
        elif len(str(row['Explanation'])) > 200:
            warnings.append(f"Row {row_num}: Explanation will be truncated to 200 characters")

        # Account validation
        if not row['Account'] or not isinstance(row['Account'], str):
            row_errors.append(f"Invalid or empty account")

        if row_errors:
            errors.append(f"Row {row_num}: {'; '.join(row_errors)}")
        else:
            valid_rows.append(idx)

    return errors, warnings, valid_rows

def sanitize_data(row):
    """Sanitize and standardize data before database insertion."""
    return {
        'date': validate_date(row['Date']),
        'description': sanitize_text(row['Description']),
        'amount': validate_amount(row['Amount']),
        'explanation': sanitize_text(row['Explanation']),
        'account': sanitize_text(row['Account'])
    }

@historical_data.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """Handle historical data upload and management."""
    try:
        if request.method == 'POST':
            if 'file' not in request.files:
                flash('No file uploaded', 'error')
                return redirect(url_for('historical_data.upload'))

            file = request.files['file']
            if not file.filename:
                flash('No file selected', 'error')
                return redirect(url_for('historical_data.upload'))

            if not validate_file_type(file.filename):
                flash('Invalid file format. Please upload a CSV or Excel file.', 'error')
                return redirect(url_for('historical_data.upload'))

            try:
                # Read the file
                if file.filename.endswith('.xlsx'):
                    df = pd.read_excel(file)
                else:
                    df = pd.read_csv(file)

                # Validate data frame structure and content
                validation_errors, warnings, valid_rows = validate_data_frame(df)
                if validation_errors:
                    for error in validation_errors[:5]:  # Show first 5 errors
                        flash(error, 'error')
                    for warning in warnings[:5]:
                        flash(warning, 'warning')
                    logger.error(f"Validation errors in upload: {validation_errors}")
                    return redirect(url_for('historical_data.upload'))

                # Get available accounts for mapping
                accounts = Account.query.filter_by(user_id=current_user.id).all()
                account_map = {acc.name: acc.id for acc in accounts}

                # Process each row
                success_count = 0
                error_count = 0
                errors = []

                # Initialize AI suggestions
                ai_helper = HistoricalDataAI()
                processed_data = []

                for idx in valid_rows:
                    row = df.iloc[idx]
                    try:
                        # Sanitize data
                        clean_data = sanitize_data(row)

                        # Get AI suggestions for missing details
                        suggestions = ai_helper.suggest_missing_details(clean_data)
                        if suggestions:
                            clean_data.update(suggestions)

                        # Validate account exists
                        account_id = account_map.get(clean_data['account'])
                        if not account_id:
                            error_count += 1
                            errors.append(f"Row {idx + 2}: Account not found: {clean_data['account']}")
                            continue

                        # Create historical data entry
                        historical_entry = HistoricalData(
                            date=clean_data['date'],
                            description=clean_data['description'],
                            amount=clean_data['amount'],
                            explanation=clean_data['explanation'],
                            account_id=account_id,
                            user_id=current_user.id
                        )
                        db.session.add(historical_entry)
                        success_count += 1
                        processed_data.append(clean_data)

                    except Exception as row_error:
                        logger.error(f"Error processing row {idx + 2}: {str(row_error)}")
                        error_count += 1
                        errors.append(f"Row {idx + 2}: {str(row_error)}")
                        continue

                if success_count > 0:
                    db.session.commit()

                    # Apply AI enhancements to processed data
                    enhanced_data = ai_helper.enhance_historical_data(processed_data)
                    if enhanced_data:
                        flash('AI suggestions have been generated for incomplete entries.', 'info')

                flash(f'Successfully processed {success_count} entries.', 'success')
                if error_count > 0:
                    flash(f'{error_count} entries had errors. Check logs for details.', 'warning')
                    for error in errors[:5]:  # Show first 5 errors
                        flash(error, 'error')

                return redirect(url_for('historical_data.upload'))

            except Exception as e:
                logger.error(f"Error processing file: {str(e)}")
                db.session.rollback()
                flash('Error processing file: ' + str(e), 'error')
                return redirect(url_for('historical_data.upload'))

        # GET request - show upload form and existing data
        historical_entries = HistoricalData.query.filter_by(user_id=current_user.id) \
            .order_by(HistoricalData.date.desc()) \
            .limit(100) \
            .all()

        return render_template(
            'historical_data/upload.html',
            entries=historical_entries
        )

    except Exception as e:
        logger.error(f"Error in historical_data route: {str(e)}")
        flash('An error occurred', 'error')
        return redirect(url_for('main.dashboard'))