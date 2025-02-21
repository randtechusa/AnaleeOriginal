
import logging
import time
from typing import Tuple, Optional
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from extensions import db

logger = logging.getLogger(__name__)

class DatabaseHealth:
    @staticmethod
    def check_connection() -> Tuple[bool, Optional[str]]:
        try:
            # Test query
            db.session.execute(text('SELECT 1'))
            db.session.commit()
            return True, None
        except SQLAlchemyError as e:
            error_msg = f"Database health check failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    @staticmethod
    def perform_retry(operation, max_retries: int = 5, base_delay: float = 1.0) -> Tuple[bool, Optional[str]]:
        """Execute operation with exponential backoff"""
        for attempt in range(max_retries):
            try:
                operation()
                return True, None
            except OperationalError as e:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Database operation failed (attempt {attempt + 1}/{max_retries}): {str(e)}")
                
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    error_msg = f"Operation failed after {max_retries} attempts"
                    logger.error(error_msg)
                    return False, error_msg
        
        return False, "Max retries exceeded"
