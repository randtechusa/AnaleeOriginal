"""
Bank Statement Upload Module
Handles all bank statement related functionality including:
- File upload and validation
- Statement processing
- Data extraction and storage
"""

import logging
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import pandas as pd
from models import db, BankAccount, BankStatementUpload, Transaction
from forms import BankStatementUploadForm

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import the blueprint instance from __init__.py
from . import bank_statements

@bank_statements.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """Handle bank statement upload"""
    form = BankStatementUploadForm()
    
    # Get bank accounts for the current user
    bank_accounts = BankAccount.query.filter_by(
        user_id=current_user.id,
        category='Bank'
    ).all()
    form.bank_account.choices = [(acc.id, f"{acc.link} - {acc.name}") for acc in bank_accounts]
    
    if request.method == 'POST':
        if form.validate_on_submit():
            try:
                file = form.statement_file.data
                filename = secure_filename(file.filename)
                
                # Create upload record
                upload = BankStatementUpload(
                    filename=filename,
                    bank_account_id=form.bank_account.data,
                    user_id=current_user.id,
                    status='Processing'
                )
                db.session.add(upload)
                db.session.commit()
                
                # Process the file
                df = pd.read_excel(file) if filename.endswith('.xlsx') else pd.read_csv(file)
                
                # Validate required columns
                required_columns = ['Date', 'Description', 'Amount']
                missing_columns = [col for col in required_columns if col not in df.columns]
                if missing_columns:
                    raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")
                
                # Process transactions
                total_rows = len(df)
                processed_rows = 0
                
                for _, row in df.iterrows():
                    transaction = Transaction(
                        date=pd.to_datetime(row['Date']).date(),
                        description=row['Description'],
                        amount=float(row['Amount']),
                        account_id=form.bank_account.data,
                        user_id=current_user.id,
                        upload_id=upload.id
                    )
                    db.session.add(transaction)
                    processed_rows += 1
                    
                    # Update progress periodically
                    if processed_rows % 100 == 0 or processed_rows == total_rows:
                        progress = {
                            'status': 'Processing transactions...',
                            'processed_rows': processed_rows,
                            'total_rows': total_rows
                        }
                        logger.info(f"Processing progress: {progress}")
                
                # Update upload status
                upload.status = 'Completed'
                upload.processed_rows = total_rows
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'message': 'Bank statement uploaded successfully'
                })
                
            except Exception as e:
                logger.error(f"Error processing bank statement: {str(e)}")
                db.session.rollback()
                return jsonify({
                    'success': False,
                    'error': f"Error processing bank statement: {str(e)}"
                }), 400
                
    # Get recent uploads for display
    recent_uploads = BankStatementUpload.query.filter_by(
        user_id=current_user.id
    ).order_by(BankStatementUpload.created_at.desc()).limit(10).all()
    
    return render_template('bank_statements/upload.html',
                         form=form,
                         recent_uploads=recent_uploads)

@bank_statements.route('/statement/<int:upload_id>')
@login_required
def view_statement(upload_id):
    """View uploaded bank statement details"""
    upload = BankStatementUpload.query.filter_by(
        id=upload_id,
        user_id=current_user.id
    ).first_or_404()
    
    transactions = Transaction.query.filter_by(
        upload_id=upload_id
    ).order_by(Transaction.date).all()
    
    return render_template('bank_statements/view.html',
                         upload=upload,
                         transactions=transactions)
