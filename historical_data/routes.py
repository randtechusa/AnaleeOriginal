import logging
import pandas as pd
from datetime import datetime
from flask import request, render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from models import db, Account, HistoricalData
from . import historical_data

logger = logging.getLogger(__name__)

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

            if not file.filename.endswith(('.csv', '.xlsx')):
                flash('Invalid file format. Please upload a CSV or Excel file.', 'error')
                return redirect(url_for('historical_data.upload'))

            try:
                # Read the file
                if file.filename.endswith('.xlsx'):
                    df = pd.read_excel(file)
                else:
                    df = pd.read_csv(file)

                # Validate required columns
                required_columns = ['Date', 'Description', 'Amount', 'Explanation', 'Account']
                missing_columns = [col for col in required_columns if col not in df.columns]
                
                if missing_columns:
                    flash(f'Missing required columns: {", ".join(missing_columns)}', 'error')
                    return redirect(url_for('historical_data.upload'))

                # Get available accounts for mapping
                accounts = Account.query.filter_by(user_id=current_user.id).all()
                account_map = {acc.name: acc.id for acc in accounts}

                # Process each row
                success_count = 0
                error_count = 0
                errors = []

                for idx, row in df.iterrows():
                    try:
                        # Validate and clean data
                        account_name = str(row['Account']).strip()
                        account_id = account_map.get(account_name)

                        if not account_id:
                            error_count += 1
                            errors.append(f"Row {idx + 2}: Account not found: {account_name}")
                            continue

                        try:
                            amount = float(row['Amount'])
                        except (ValueError, TypeError):
                            error_count += 1
                            errors.append(f"Row {idx + 2}: Invalid amount value")
                            continue

                        try:
                            date = pd.to_datetime(row['Date']).date()
                        except (ValueError, TypeError):
                            error_count += 1
                            errors.append(f"Row {idx + 2}: Invalid date format")
                            continue

                        # Create historical data entry
                        historical_entry = HistoricalData(
                            date=date,
                            description=str(row['Description']),
                            amount=amount,
                            explanation=str(row['Explanation']),
                            account_id=account_id,
                            user_id=current_user.id
                        )
                        db.session.add(historical_entry)
                        success_count += 1

                    except Exception as row_error:
                        logger.error(f"Error processing row {idx + 2}: {str(row_error)}")
                        error_count += 1
                        errors.append(f"Row {idx + 2}: {str(row_error)}")
                        continue

                if success_count > 0:
                    db.session.commit()
                    
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
