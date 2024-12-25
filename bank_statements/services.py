"""
Service layer for bank statement processing
Handles business logic separately from routes
"""
import logging
import os
from typing import Tuple, Dict, Any
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
from models import db, BankStatementUpload  # Updated import from main models.py
from .excel_reader import BankStatementExcelReader

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
        Process a bank statement upload
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

            # Save file temporarily
            temp_path = os.path.join('/tmp', secure_filename(file.filename))
            file.save(temp_path)

            try:
                # Read and validate Excel file
                df = self.excel_reader.read_excel(temp_path)
                if df is None:
                    upload.set_error('; '.join(self.excel_reader.get_errors()))
                    db.session.commit()
                    return False, {
                        'success': False,
                        'error': 'Error reading bank statement',
                        'errors': self.excel_reader.get_errors()
                    }

                # Validate data
                if not self.excel_reader.validate_data(df):
                    upload.set_error('; '.join(self.excel_reader.get_errors()))
                    db.session.commit()
                    return False, {
                        'success': False,
                        'error': 'Invalid bank statement data',
                        'errors': self.excel_reader.get_errors()
                    }

                # If everything is valid, mark as success
                upload.set_success(f"Processed {len(df)} transactions")
                db.session.commit()

                return True, {
                    'success': True,
                    'message': f'Successfully processed {len(df)} transactions',
                    'rows_processed': len(df)
                }

            finally:
                # Clean up temporary file
                if os.path.exists(temp_path):
                    os.remove(temp_path)

        except Exception as e:
            logger.error(f"Error processing bank statement: {str(e)}")
            if 'upload' in locals():
                upload.set_error(str(e))
                db.session.commit()
            return False, {
                'success': False,
                'error': f'Error processing bank statement: {str(e)}'
            }