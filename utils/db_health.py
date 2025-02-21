
import logging
import time
from typing import Tuple, Optional, Dict
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from extensions import db

logger = logging.getLogger(__name__)
handler = logging.FileHandler('database.log')
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

class DatabaseHealth:
    _instance = None
    _health_metrics = {
        'last_check': None,
        'consecutive_failures': 0,
        'total_failures': 0,
        'avg_response_time': 0,
        'total_checks': 0
    }

    @staticmethod
    def get_instance():
        if DatabaseHealth._instance is None:
            DatabaseHealth._instance = DatabaseHealth()
        return DatabaseHealth._instance

    @staticmethod
    def check_connection() -> Tuple[bool, Optional[str]]:
        start_time = time.time()
        try:
            db.session.execute(text('SELECT 1'))
            db.session.commit()
            
            # Update metrics
            elapsed = time.time() - start_time
            DatabaseHealth._health_metrics['avg_response_time'] = (
                (DatabaseHealth._health_metrics['avg_response_time'] * 
                 DatabaseHealth._health_metrics['total_checks'] + elapsed) /
                (DatabaseHealth._health_metrics['total_checks'] + 1)
            )
            DatabaseHealth._health_metrics['total_checks'] += 1
            DatabaseHealth._health_metrics['last_check'] = datetime.now()
            DatabaseHealth._health_metrics['consecutive_failures'] = 0
            
            return True, None
        except SQLAlchemyError as e:
            error_msg = f"Database health check failed: {str(e)}"
            logger.error(error_msg)
            DatabaseHealth._health_metrics['consecutive_failures'] += 1
            DatabaseHealth._health_metrics['total_failures'] += 1
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
            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                logger.error(error_msg)
                return False, error_msg

        return False, "Max retries exceeded"

    @staticmethod
    def get_health_metrics() -> Dict:
        """Get current health metrics"""
        return DatabaseHealth._health_metrics

    @staticmethod
    def should_failover() -> bool:
        """Determine if failover should be triggered"""
        metrics = DatabaseHealth._health_metrics
        return (metrics['consecutive_failures'] >= 3 or
                (metrics['last_check'] and 
                 datetime.now() - metrics['last_check'] > timedelta(minutes=5)))
