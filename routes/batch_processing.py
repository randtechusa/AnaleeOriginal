"""
Batch Transaction Processing Routes
Handles all batch processing related functionality while maintaining separation from core features.
"""
from flask import Blueprint, render_template, request, jsonify, Response, stream_with_context
from flask_login import login_required, current_user
import logging
import pandas as pd
from models import db, Transaction, Account
from utils.validation import validate_transaction_data
from utils.sanitization import sanitize_transaction_data
import json

# Configure logging
logger = logging.getLogger(__name__)

batch_processing = Blueprint('batch_processing', __name__)

@batch_processing.route('/')
@login_required
def batch_process_page():
    """Render the batch processing interface."""
    try:
        return render_template('batch_processing.html')
    except Exception as e:
        logger.error(f"Error rendering batch processing page: {str(e)}")
        return jsonify({'error': 'Error loading batch processing interface'}), 500

@batch_processing.route('/process', methods=['POST'])
@login_required
def process_transactions():
    """Handle the batch processing of transactions."""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['file']
        if not file.filename:
            return jsonify({'error': 'No file selected'}), 400

        try:
            # Read file based on extension
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

                for batch_num in range(total_batches):
                    start_idx = batch_num * batch_size
                    end_idx = min(start_idx + batch_size, total_rows)
                    batch_df = df.iloc[start_idx:end_idx]

                    success, failure, warnings, errors = process_batch(batch_df, batch_num + 1, total_batches)

                    total_success += success
                    total_failure += failure
                    total_warnings += warnings

                    processed_rows = min((batch_num + 1) * batch_size, total_rows)
                    overall_progress = (processed_rows / total_rows) * 100

                    progress_data = {
                        'overall_progress': overall_progress,
                        'batch_progress': 100,
                        'processed_count': processed_rows,
                        'total_count': total_rows,
                        'current_batch': batch_num + 1,
                        'total_batches': total_batches,
                        'success_count': total_success,
                        'failure_count': total_failure,
                        'warning_count': total_warnings,
                        'errors': errors[-5:] if errors else [],
                        'status': f'Processing batch {batch_num + 1}/{total_batches}'
                    }
                    yield f"data: {json.dumps(progress_data)}\n\n"

                # Final summary
                summary_data = {
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
                }
                yield f"data: {json.dumps(summary_data)}\n\n"

            return Response(
                stream_with_context(generate_updates()),
                mimetype='text/event-stream'
            )

        except Exception as e:
            logger.error(f"Error processing batch file: {str(e)}")
            return jsonify({'error': str(e)}), 500

    except Exception as e:
        logger.error(f"Error in batch processing endpoint: {str(e)}")
        return jsonify({'error': str(e)}), 500

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