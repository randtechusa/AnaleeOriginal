"""Routes for handling historical data uploads and processing"""
import logging
import pandas as pd
from datetime import datetime
from flask import request, render_template, flash, redirect, url_for, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import re
from decimal import Decimal, InvalidOperation
from flask_wtf import FlaskForm
from wtforms import FileField, SubmitField, SelectField
from wtforms.validators import DataRequired

from models import db, Account, HistoricalData
from . import historical_data

# Configure logging
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
    """Handle historical data upload and processing."""
    try:
        form = UploadForm()
        logger.info("Processing upload request")

        if request.method == 'POST':
            logger.info("Received POST request")

            if not form.validate_on_submit():
                logger.error("Form validation failed")
                for field, errors in form.errors.items():
                    for error in errors:
                        logger.error(f"Form error - {field}: {error}")
                        flash(f"{field}: {error}", 'error')
                return redirect(url_for('historical_data.upload'))

            try:
                # Get selected bank account
                account_id = int(form.account.data)
                account = Account.query.get(account_id)
                if not account or account.user_id != current_user.id:
                    logger.error(f"Invalid account selected: {account_id}")
                    flash('Invalid bank account selected', 'error')
                    return redirect(url_for('historical_data.upload'))

                # Process file upload
                file = form.file.data
                if not file or not file.filename:
                    logger.error("No file selected")
                    flash('No file selected', 'error')
                    return redirect(url_for('historical_data.upload'))

                filename = secure_filename(file.filename)
                if not filename.lower().endswith(('.csv', '.xlsx')):
                    logger.error(f"Invalid file type: {filename}")
                    flash('Invalid file format. Please upload a CSV or Excel file.', 'error')
                    return redirect(url_for('historical_data.upload'))

                # Read file contents
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

                    # Process rows
                    success_count = 0
                    error_count = 0

                    for _, row in df.iterrows():
                        try:
                            date = pd.to_datetime(row['Date']).date()
                            amount = Decimal(str(row['Amount']))
                            description = str(row['Description']).strip()[:200]
                            explanation = str(row.get('Explanation', '')).strip()[:200]

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
                        except Exception as e:
                            logger.error(f"Error processing row: {str(e)}")
                            error_count += 1
                            continue

                    if success_count > 0:
                        db.session.commit()
                        flash(f'Successfully processed {success_count} entries.', 'success')
                        logger.info(f"Successfully processed {success_count} entries")

                    if error_count > 0:
                        flash(f'{error_count} entries had errors.', 'warning')
                        logger.warning(f"{error_count} entries had errors")

                    return redirect(url_for('historical_data.upload'))

                except Exception as e:
                    logger.error(f"Error processing file: {str(e)}")
                    db.session.rollback()
                    flash('Error processing file: ' + str(e), 'error')
                    return redirect(url_for('historical_data.upload'))

            except Exception as e:
                logger.error(f"Error processing upload: {str(e)}")
                flash('Error processing upload: ' + str(e), 'error')
                return redirect(url_for('historical_data.upload'))

        # GET request - show upload form
        return render_template('historical_data/upload.html', form=form)

    except Exception as e:
        logger.error(f"Error in upload route: {str(e)}")
        flash('An error occurred', 'error')
        return redirect(url_for('historical_data.upload'))