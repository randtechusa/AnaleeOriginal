"""
Service layer for bank statement processing
Handles business logic separately from routes
Enhanced with user-friendly error notifications
"""
import logging
import os
from typing import Tuple, Dict, Any
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

    def process_upload(self, file, account_id, user_id):
        """Process the uploaded bank statement"""
        try:
            # Save file temporarily
            filename = secure_filename(file.filename)
            temp_path = os.path.join('uploads', str(user_id), filename)
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            file.save(temp_path)
            
            # Process the file
            df = self.excel_reader.read_excel(temp_path)
            if df is None:
                return False, {"error": "Failed to read bank statement file", "details": self.excel_reader.get_errors()}
                
            return True, {"message": "File processed successfully", "rows": len(df)}
            
        except Exception as e:
            logger.error(f"Error processing upload: {str(e)}")
            return False, {"error": "Error processing file", "details": [str(e)]}

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
            'unknown': "An unexpected error occurred. Please try again or contact support.",
            'file_save_error': "Failed to save the uploaded file. Please try again."
        }
        base_message = error_messages.get(error_type, error_messages['unknown'])
        if details:
            return f"{base_message} Details: {details}"
        return base_message

    def process_upload(
        self,
        file,
        account_id: int,
        user_id: int
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Process a bank statement upload with enhanced error handling and validation
        Returns (success, response_data)
        """
        try:
            logger.info(f"Starting to process upload for user {user_id}, account {account_id}")

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
                logger.error(f"Invalid file type: {file_ext}")
                return False, {
                    'success': False,
                    'error': error_msg,
                    'error_type': 'file_type'
                }

            # Save file temporarily with proper error handling
            try:
                temp_path = os.path.join('/tmp', secure_filename(file.filename))
                file.save(temp_path)
                logger.info(f"Saved temporary file to: {temp_path}")
            except Exception as e:
                error_msg = self.get_friendly_error_message('file_save_error', str(e))
                upload.set_error(error_msg)
                db.session.commit()
                logger.error(f"File save error: {str(e)}")
                return False, {
                    'success': False,
                    'error': error_msg,
                    'error_type': 'file_save_error'
                }

            try:
                # Read and validate Excel file
                df = self.excel_reader.read_excel(temp_path)
                logger.info("Successfully read Excel file")

                if df is None or df.empty:
                    error_msg = self.get_friendly_error_message('empty_file')
                    upload.set_error(error_msg)
                    db.session.commit()
                    logger.error("Empty file detected")
                    return False, {
                        'success': False,
                        'error': error_msg,
                        'error_type': 'empty_file'
                    }

                # Process successful
                upload.set_success(f"Successfully processed {len(df)} rows")
                db.session.commit()

                return True, {
                    'success': True,
                    'message': 'File processed successfully',
                    'rows_processed': len(df) if df is not None else 0
                }

            finally:
                # Clean up temporary file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    logger.info("Cleaned up temporary file")

        except Exception as e:
            logger.error(f"Error processing bank statement: {str(e)}", exc_info=True)
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