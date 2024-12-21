import logging
import pandas as pd
from datetime import datetime
from flask import request, render_template, flash, redirect, url_for, jsonify
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
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['file']
        if not file.filename:
            return jsonify({'error': 'No file selected'}), 400

        if not validate_file_type(file.filename):
            return jsonify({'error': 'Invalid file format. Please upload a CSV or Excel file.'}), 400

        try:
            # Read the file
            if file.filename.endswith('.xlsx'):
                df = pd.read_excel(file)
            else:
                df = pd.read_csv(file)

            # Get preview results
            preview_results = preview_data_frame(df)

            # Add summary statistics
            preview_results['summary'] = {
                'total_rows': len(df),
                'valid_rows': len(preview_results['valid_rows']),
                'invalid_rows': len(preview_results['invalid_rows']),
                'warnings': len(preview_results['warnings'])
            }

            return jsonify(preview_results)

        except Exception as e:
            logger.error(f"Error processing file for preview: {str(e)}")
            return jsonify({'error': f'Error processing file: {str(e)}'}), 500

    except Exception as e:
        logger.error(f"Error in preview route: {str(e)}")
        return jsonify({'error': str(e)}), 500

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