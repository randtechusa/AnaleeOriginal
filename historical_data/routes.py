import logging
import pandas as pd
from datetime import datetime
from flask import request, render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from models import db, Account, HistoricalData
from . import historical_data
from .ai_suggestions import HistoricalDataAI

logger = logging.getLogger(__name__)

def validate_file_type(filename):
    """Validate if the uploaded file is CSV or Excel."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'csv', 'xlsx'}

def validate_data_frame(df):
    """Validate the structure and content of the uploaded data."""
    errors = []

    # Check required columns
    required_columns = ['Date', 'Description', 'Amount', 'Explanation', 'Account']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        errors.append(f"Missing required columns: {', '.join(missing_columns)}")
        return errors

    # Validate each column
    for idx, row in df.iterrows():
        row_num = idx + 2  # Add 2 because idx starts at 0 and we skip header row

        # Date validation
        try:
            pd.to_datetime(row['Date'])
        except (ValueError, TypeError):
            errors.append(f"Row {row_num}: Invalid date format")

        # Description validation
        if not isinstance(row['Description'], str) or not row['Description'].strip():
            errors.append(f"Row {row_num}: Invalid or empty description")

        # Amount validation
        try:
            float(row['Amount'])
        except (ValueError, TypeError):
            errors.append(f"Row {row_num}: Invalid amount value")

        # Explanation validation
        if not isinstance(row['Explanation'], str) or not row['Explanation'].strip():
            errors.append(f"Row {row_num}: Invalid or empty explanation")

        # Account validation (will be checked against database later)
        if not isinstance(row['Account'], str) or not row['Account'].strip():
            errors.append(f"Row {row_num}: Invalid or empty account")

    return errors

def sanitize_data(row):
    """Sanitize and standardize data before database insertion."""
    return {
        'date': pd.to_datetime(row['Date']).date(),
        'description': str(row['Description']).strip()[:200],  # Limit to 200 chars
        'amount': float(row['Amount']),
        'explanation': str(row['Explanation']).strip()[:200],  # Limit to 200 chars
        'account': str(row['Account']).strip()
    }

@historical_data.route('/', methods=['GET', 'POST'])
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
                validation_errors = validate_data_frame(df)
                if validation_errors:
                    for error in validation_errors[:5]:  # Show first 5 errors
                        flash(error, 'error')
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

                for idx, row in df.iterrows():
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
        historical_entries = HistoricalData.query.filter_by(user_id=current_user.id)\
            .order_by(HistoricalData.date.desc())\
            .limit(100)\
            .all()

        return render_template(
            'historical_data/upload.html',
            entries=historical_entries
        )

    except Exception as e:
        logger.error(f"Error in historical_data route: {str(e)}")
        flash('An error occurred', 'error')
        return redirect(url_for('main.dashboard'))