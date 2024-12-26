"""
Service layer for bank statement processing
Handles business logic separately from routes
Enhanced with user-friendly error notifications
"""
import logging
import os
from typing import Tuple, Dict, Any
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
from .models import BankStatementUpload
from .excel_reader import BankStatementExcelReader
from models import db, Transaction

logger = logging.getLogger(__name__)

class BankStatementService:
    """Service for handling bank statement uploads and processing"""

    def __init__(self):
        self.excel_reader = BankStatementExcelReader()
        self.errors = []

    def get_friendly_error_message(self, error_type: str, details: str = None) -> str:
        """
        Convert technical errors into user-friendly messages
        """
        error_messages = {
            'file_type': "Please upload only Excel (.xlsx) or CSV (.csv) files.",
            'missing_columns': "Your file is missing required columns. Please ensure it includes: Date, Description, and Amount.",
            'invalid_date': "Some dates in your statement are not in the correct format. Please check the date format.",
            'invalid_amount': "Some amounts are not in the correct format. Please ensure amounts are numbers.",
            'future_date': "We noticed some future dates in your statement. Please check the dates.",
            'empty_file': "The uploaded file appears to be empty. Please check the file contents.",
            'processing_error': "We encountered an issue while processing your file. Please try again.",
            'db_error': "There was a problem saving your data. Please try again.",
            'unknown': "An unexpected error occurred. Please try again or contact support."
        }
        base_message = error_messages.get(error_type, error_messages['unknown'])
        if details:
            return f"{base_message} Details: {details}"
        return base_message

    def process_upload(
        self,
        file: FileStorage,
        account_id: int,
        user_id: int
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Process a bank statement upload with enhanced error handling and validation
        Returns (success, response_data)
        """
        try:
            # Create upload record with improved tracking
            upload = BankStatementUpload(
                filename=secure_filename(file.filename),
                account_id=account_id,
                user_id=user_id,
                status='processing'
            )
            db.session.add(upload)
            db.session.commit()
            logger.info(f"Created upload record for file: {file.filename}")

            # Validate file extension
            file_ext = os.path.splitext(secure_filename(file.filename))[1].lower()
            if file_ext not in ['.csv', '.xlsx']:
                error_msg = self.get_friendly_error_message('file_type')
                upload.set_error(error_msg)
                db.session.commit()
                return False, {
                    'success': False,
                    'error': error_msg,
                    'error_type': 'file_type'
                }

            # Save file temporarily
            temp_path = os.path.join('/tmp', secure_filename(file.filename))
            file.save(temp_path)
            logger.info(f"Saved temporary file to: {temp_path}")

            try:
                # Read and validate Excel file
                df = self.excel_reader.read_excel(temp_path)
                if df is None:
                    error_msg = self.get_friendly_error_message(
                        'processing_error',
                        '; '.join(self.excel_reader.get_errors())
                    )
                    logger.error(f"Excel reading failed: {error_msg}")
                    upload.set_error(error_msg)
                    db.session.commit()
                    return False, {
                        'success': False,
                        'error': error_msg,
                        'error_type': 'processing_error',
                        'details': self.excel_reader.get_errors()
                    }

                # Validate data with improved error feedback
                if not self.excel_reader.validate_data(df):
                    error_type = 'missing_columns' if any('missing' in err.lower() for err in self.excel_reader.get_errors()) else 'processing_error'
                    error_msg = self.get_friendly_error_message(
                        error_type,
                        '; '.join(self.excel_reader.get_errors())
                    )
                    logger.error(f"Data validation failed: {error_msg}")
                    upload.set_error(error_msg)
                    db.session.commit()
                    return False, {
                        'success': False,
                        'error': error_msg,
                        'error_type': error_type,
                        'details': self.excel_reader.get_errors()
                    }

                # Process transactions with enhanced progress tracking
                transactions_created = 0
                errors = []
                processing_notes = []

                # Sort by date to maintain chronological order
                df = df.sort_values('Date')

                for _, row in df.iterrows():
                    try:
                        # Create transaction record with validation
                        transaction = Transaction(
                            date=row['Date'].date(),  # Convert to date only
                            description=str(row['Description']).strip(),
                            amount=float(row['Amount']),  # Convert to float
                            account_id=account_id,
                            user_id=user_id,
                            status='pending',  # Mark as pending for iCountant processing
                            source='bank_statement'
                        )
                        db.session.add(transaction)
                        transactions_created += 1

                        if transactions_created % 100 == 0:  # Log progress for large files
                            processing_notes.append(f"Processed {transactions_created} transactions")

                    except Exception as e:
                        error_msg = f"Error processing row: {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                        continue

                if transactions_created == 0:
                    error_msg = self.get_friendly_error_message('processing_error', "No valid transactions found in file")
                    upload.set_error(error_msg)
                    db.session.commit()
                    return False, {
                        'success': False,
                        'error': error_msg,
                        'error_type': 'processing_error',
                        'details': errors
                    }

                # Commit all valid transactions
                try:
                    db.session.commit()
                    logger.info(f"Successfully committed {transactions_created} transactions")
                except Exception as e:
                    logger.error(f"Error committing transactions: {str(e)}")
                    db.session.rollback()
                    error_msg = self.get_friendly_error_message('db_error', str(e))
                    upload.set_error(error_msg)
                    db.session.commit()
                    return False, {
                        'success': False,
                        'error': error_msg,
                        'error_type': 'db_error',
                        'details': [str(e)]
                    }

                # Mark upload as successful with detailed notes
                processing_notes.append(f"Successfully processed {transactions_created} transactions")
                upload.set_success('\n'.join(processing_notes))
                db.session.commit()

                return True, {
                    'success': True,
                    'message': f'Successfully processed {transactions_created} transactions',
                    'rows_processed': transactions_created,
                    'processing_notes': processing_notes
                }

            finally:
                # Clean up temporary file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    logger.info("Cleaned up temporary file")

        except Exception as e:
            logger.error(f"Error processing bank statement: {str(e)}")
            error_msg = self.get_friendly_error_message('unknown', str(e))
            if 'upload' in locals():
                upload.set_error(error_msg)
                db.session.commit()
            return False, {
                'success': False,
                'error': error_msg,
                'error_type': 'unknown',
                'details': [str(e)]
            }