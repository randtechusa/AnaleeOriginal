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
    _health_metrics = {
        'last_check': None,
        'consecutive_failures': 0,
        'total_checks': 0,
        'avg_response_time': 0,
        'total_failures': 0,
        'failover_count': 0,
        'last_failover': None
    }

    _instance = None

    @staticmethod
    def get_instance():
        if DatabaseHealth._instance is None:
            DatabaseHealth._instance = DatabaseHealth()
        return DatabaseHealth._instance

    @staticmethod
    def check_connection(uri: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        try:
            start_time = time.time()
            if uri:
                from sqlalchemy import create_engine
                engine = create_engine(uri, 
                    pool_pre_ping=True,
                    pool_recycle=3600,
                    connect_args={'connect_timeout': 10}
                )
                with engine.connect() as conn:
                    conn.execute(text('SELECT 1'))
            else:
                db.session.execute(text('SELECT 1'))
                db.session.commit()

            elapsed = time.time() - start_time
            DatabaseHealth._update_metrics(elapsed, success=True)
            return True, None

        except SQLAlchemyError as e:
            error_msg = f"Database health check failed: {str(e)}"
            logger.error(error_msg)
            DatabaseHealth._update_metrics(0, success=False)
            return False, error_msg

    @staticmethod
    def _update_metrics(elapsed: float, success: bool):
        metrics = DatabaseHealth._health_metrics
        metrics['last_check'] = datetime.now()
        metrics['total_checks'] += 1

        if success:
            metrics['consecutive_failures'] = 0
            metrics['avg_response_time'] = (
                (metrics['avg_response_time'] * (metrics['total_checks'] - 1) + elapsed) /
                metrics['total_checks']
            )
        else:
            metrics['consecutive_failures'] += 1
            metrics['total_failures'] += 1

    @staticmethod
    def perform_failover() -> Tuple[bool, Optional[str]]:
        """Execute database failover procedure"""
        from config import Config
        metrics = DatabaseHealth._health_metrics

        try:
            backup_uri = Config.SQLALCHEMY_DATABASE_URI_BACKUP
            if not backup_uri:
                return False, "No backup database configured"

            # Test backup connection
            success, error = DatabaseHealth.check_connection(backup_uri)
            if success:
                # Update active connection
                Config.SQLALCHEMY_DATABASE_URI = backup_uri
                db.get_engine().dispose()

                metrics['failover_count'] += 1
                metrics['last_failover'] = datetime.now()

                logger.info("Database failover executed successfully")
                return True, None
            else:
                return False, f"Backup database check failed: {error}"

        except Exception as e:
            error_msg = f"Failover failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    @staticmethod
    def get_health_metrics() -> Dict:
        """Get current health metrics"""
        metrics = DatabaseHealth._health_metrics.copy()
        metrics['status'] = 'healthy' if metrics['consecutive_failures'] == 0 else 'degraded'
        return metrics

    @staticmethod
    def should_failover() -> bool:
        """Determine if failover should be triggered"""
        metrics = DatabaseHealth._health_metrics
        time_threshold = timedelta(minutes=5)

        return (
            metrics['consecutive_failures'] >= 3 or
            (metrics['last_check'] and datetime.now() - metrics['last_check'] > time_threshold) or
            (metrics['last_failover'] and 
             datetime.now() - metrics['last_failover'] > timedelta(hours=1) and
             metrics['consecutive_failures'] > 0)
        )