"""
Service layer for bank statement processing
Handles business logic separately from routes
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
            # Create upload record
            upload = BankStatementUpload(
                filename=secure_filename(file.filename),
                account_id=account_id,
                user_id=user_id,
                status='processing'
            )
            db.session.add(upload)
            db.session.commit()
            logger.info(f"Created upload record for file: {file.filename}")

            # Save file temporarily
            temp_path = os.path.join('/tmp', secure_filename(file.filename))
            file.save(temp_path)
            logger.info(f"Saved temporary file to: {temp_path}")

            try:
                # Read and validate Excel file
                df = self.excel_reader.read_excel(temp_path)
                if df is None:
                    error_msg = '; '.join(self.excel_reader.get_errors())
                    logger.error(f"Excel reading failed: {error_msg}")
                    upload.set_error(error_msg)
                    db.session.commit()
                    return False, {
                        'success': False,
                        'error': 'Error reading bank statement',
                        'errors': self.excel_reader.get_errors()
                    }

                # Validate data
                if not self.excel_reader.validate_data(df):
                    error_msg = '; '.join(self.excel_reader.get_errors())
                    logger.error(f"Data validation failed: {error_msg}")
                    upload.set_error(error_msg)
                    db.session.commit()
                    return False, {
                        'success': False,
                        'error': 'Invalid bank statement data',
                        'errors': self.excel_reader.get_errors()
                    }

                # Process transactions
                transactions_created = 0
                errors = []

                # Sort by date to maintain chronological order
                df = df.sort_values('Date')

                for _, row in df.iterrows():
                    try:
                        # Create transaction record
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
                    except Exception as e:
                        error_msg = f"Error processing row: {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                        continue

                if transactions_created == 0:
                    upload.set_error("No valid transactions found in file")
                    db.session.commit()
                    return False, {
                        'success': False,
                        'error': 'No valid transactions found',
                        'errors': errors
                    }

                # Commit all valid transactions
                try:
                    db.session.commit()
                    logger.info(f"Successfully committed {transactions_created} transactions")
                except Exception as e:
                    logger.error(f"Error committing transactions: {str(e)}")
                    db.session.rollback()
                    upload.set_error(f"Database error: {str(e)}")
                    db.session.commit()
                    return False, {
                        'success': False,
                        'error': 'Error saving transactions',
                        'errors': [str(e)]
                    }

                # Mark upload as successful
                upload.set_success(f"Processed {transactions_created} transactions")
                db.session.commit()

                return True, {
                    'success': True,
                    'message': f'Successfully processed {transactions_created} transactions',
                    'rows_processed': transactions_created
                }

            finally:
                # Clean up temporary file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    logger.info("Cleaned up temporary file")

        except Exception as e:
            logger.error(f"Error processing bank statement: {str(e)}")
            if 'upload' in locals():
                upload.set_error(str(e))
                db.session.commit()
            return False, {
                'success': False,
                'error': f'Error processing bank statement: {str(e)}'
            }