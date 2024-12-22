"""
Batch Transaction Processing Handler
This module handles large-scale transaction processing in batches.
It is designed to work alongside the core transaction system without affecting existing functionality.
"""
import logging
import pandas as pd
from flask import Blueprint, request, Response, stream_with_context, jsonify
from flask_login import login_required, current_user
import json
from datetime import datetime
import time

from models import db, Transaction, Account
from utils.validation import validate_transaction_data
from utils.sanitization import sanitize_transaction_data

logger = logging.getLogger(__name__)

batch_processing = Blueprint('batch_processing', __name__)

def process_batch(batch_df, batch_num, total_batches):
    """Process a single batch of transactions."""
    batch_size = len(batch_df)
    processed = 0
    success_count = 0
    failure_count = 0
    warning_count = 0
    errors = []

    try:
        for idx, row in batch_df.iterrows():
            try:
                # Validate data
                validated_data = validate_transaction_data(row)
                if not validated_data['is_valid']:
                    failure_count += 1
                    errors.extend(validated_data['errors'])
                    continue

                # Sanitize data
                clean_data = sanitize_transaction_data(validated_data['data'])
                
                # Create transaction without affecting existing data
                transaction = Transaction(
                    date=clean_data['date'],
                    description=clean_data['description'],
                    amount=clean_data['amount'],
                    account_id=clean_data['account_id'],
                    user_id=current_user.id
                )
                
                db.session.add(transaction)
                success_count += 1
                
            except Exception as e:
                logger.error(f"Error processing row {idx}: {str(e)}")
                failure_count += 1
                errors.append(f"Row {idx}: {str(e)}")
                
            processed += 1
            
            # Yield progress update
            if processed % 10 == 0 or processed == batch_size:
                yield {
                    'batch_progress': (processed / batch_size) * 100,
                    'current_batch': batch_num,
                    'total_batches': total_batches,
                    'success_count': success_count,
                    'failure_count': failure_count,
                    'warning_count': warning_count,
                    'errors': errors[-5:] if errors else [],  # Show last 5 errors
                    'status': f'Processing batch {batch_num}/{total_batches} - {processed}/{batch_size} rows'
                }
                
        # Commit batch
        try:
            db.session.commit()
        except Exception as e:
            logger.error(f"Error committing batch {batch_num}: {str(e)}")
            db.session.rollback()
            failure_count = batch_size
            errors.append(f"Batch {batch_num} commit failed: {str(e)}")
            
    except Exception as e:
        logger.error(f"Error processing batch {batch_num}: {str(e)}")
        errors.append(f"Batch {batch_num} processing failed: {str(e)}")
        
    return success_count, failure_count, warning_count, errors

@batch_processing.route('/batch-process', methods=['POST'])
@login_required
def process_transactions():
    """Handle batch processing of transactions with progress updates."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400

    try:
        # Read file
        if file.filename.endswith('.xlsx'):
            df = pd.read_excel(file, engine='openpyxl')
        else:
            df = pd.read_csv(file)

        total_rows = len(df)
        batch_size = int(request.form.get('batch_size', 100))
        total_batches = (total_rows + batch_size - 1) // batch_size
        
        def generate_updates():
            """Generate progress updates for streaming response."""
            total_success = 0
            total_failure = 0
            total_warnings = 0
            processed_rows = 0
            
            for batch_num in range(total_batches):
                start_idx = batch_num * batch_size
                end_idx = min(start_idx + batch_size, total_rows)
                batch_df = df.iloc[start_idx:end_idx]
                
                for update in process_batch(batch_df, batch_num + 1, total_batches):
                    processed_rows = batch_num * batch_size + int(update['batch_progress'] * batch_size / 100)
                    overall_progress = (processed_rows / total_rows) * 100
                    
                    update.update({
                        'overall_progress': overall_progress,
                        'processed_count': processed_rows,
                        'total_count': total_rows,
                    })
                    
                    yield f"data: {json.dumps(update)}\n\n"
                    
            # Final summary
            yield f"data: {json.dumps({
                'overall_progress': 100,
                'batch_progress': 100,
                'processed_count': total_rows,
                'total_count': total_rows,
                'current_batch': total_batches,
                'total_batches': total_batches,
                'success_count': total_success,
                'failure_count': total_failure,
                'warning_count': total_warnings,
                'status': 'Processing completed'
            })}\n\n"
            
        return Response(
            stream_with_context(generate_updates()),
            mimetype='text/event-stream'
        )
        
    except Exception as e:
        logger.error(f"Error in batch processing: {str(e)}")
        return jsonify({'error': str(e)}), 500

@batch_processing.route('/batch-process', methods=['GET'])
@login_required
def batch_process_page():
    """Render the batch processing page."""
    return render_template('batch_processing.html')
