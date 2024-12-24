"""
Service layer for bank statement processing
Handles business logic separately from routes
"""
import logging
from typing import Tuple, Dict, Any
from werkzeug.datastructures import FileStorage
from .models import BankStatementUpload
from .upload_validator import BankStatementValidator
from models import db

logger = logging.getLogger(__name__)

class BankStatementService:
    """Service for handling bank statement uploads and processing"""
    
    def __init__(self):
        self.validator = BankStatementValidator()

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
                filename=file.filename,
                account_id=account_id,
                user_id=user_id,
                status='processing'
            )
            db.session.add(upload)
            db.session.commit()

            # Validate and process file
            success = self.validator.validate_and_process(file, account_id, user_id)
            
            # Update upload status
            if success:
                upload.status = 'completed'
                response = {
                    'success': True,
                    'message': 'Bank statement processed successfully'
                }
            else:
                upload.status = 'failed'
                error_messages = self.validator.get_error_messages()
                upload.error_message = '; '.join(error_messages)
                response = {
                    'success': False,
                    'error': error_messages[0] if error_messages else 'Processing failed'
                }

            db.session.commit()
            return success, response

        except Exception as e:
            logger.error(f"Error processing bank statement: {str(e)}")
            if upload.id:
                upload.status = 'failed'
                upload.error_message = str(e)
                db.session.commit()
            return False, {
                'success': False,
                'error': f'Error processing bank statement: {str(e)}'
            }
