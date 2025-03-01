"""Database health monitoring and management utilities"""
import logging
import time
import os
import requests
from sqlalchemy import create_engine, text
from flask import current_app

logger = logging.getLogger(__name__)

class DatabaseHealth:
    """Singleton class to monitor and manage database health"""
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = DatabaseHealth()
        return cls._instance

    def __init__(self):
        self.consecutive_failures = 0
        self.last_check_time = 0
        self.max_failures_before_failover = 3
        self.check_interval = 60  # seconds

    def check_connection(self):
        """Check if the database connection is healthy"""
        try:
            if not current_app:
                logger.warning("No Flask app context available for DB health check")
                return False, "No application context"

            engine = current_app.extensions['sqlalchemy'].db.engine
            with engine.connect() as conn:
                conn.execute(text('SELECT 1'))
                self.consecutive_failures = 0
                return True, None
        except Exception as e:
            self.consecutive_failures += 1
            error_message = str(e)
            logger.error(f"Database health check failed: {error_message}")
            return False, error_message

    def should_failover(self):
        """Determine if we should initiate failover to SQLite"""
        return self.consecutive_failures >= self.max_failures_before_failover

    def perform_failover(self):
        """Switch database connection to SQLite fallback"""
        try:
            logger.warning("Initiating database failover to SQLite")

            # Get current database URI
            current_uri = current_app.config['SQLALCHEMY_DATABASE_URI']

            # Only failover if not already using SQLite
            if 'sqlite' in current_uri.lower():
                logger.info("Already using SQLite database, no failover needed")
                return True, None

            # Setup SQLite database path
            sqlite_path = os.path.join(os.getcwd(), 'instance', 'fallback.db')
            os.makedirs('instance', exist_ok=True)

            # Update configuration
            current_app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{sqlite_path}"

            # Get SQLAlchemy instance
            db = current_app.extensions['sqlalchemy'].db

            # Dispose existing connections
            db.engine.dispose()

            # Create tables in new database
            db.create_all()

            logger.info("Failover to SQLite complete")
            return True, None
        except Exception as e:
            logger.error(f"Failover failed: {str(e)}")
            return False, str(e)

    def wake_up_endpoint(self, database_url):
        """Attempt to wake up a sleeping PostgreSQL endpoint"""
        try:
            if not database_url or 'neon.tech' not in database_url.lower():
                logger.info("Not a Neon database or no URL provided")
                return False

            logger.info("Attempting to wake up Neon database endpoint")

            # Extract endpoint details
            parts = database_url.split('@')[1].split('/')[0].split(':')[0]

            # Construct engine with minimal settings for connection attempt
            wake_engine = create_engine(
                database_url,
                pool_pre_ping=True,
                pool_size=1,
                max_overflow=0,
                connect_args={'connect_timeout': 5}
            )

            # Try basic connection to wake up endpoint
            try:
                with wake_engine.connect() as conn:
                    conn.execute(text('SELECT 1'))
                    logger.info("Successfully woke up database endpoint")
                    return True
            except Exception as e:
                logger.info(f"Initial wake attempt failed: {e}")

                # If PostgreSQL serverless endpoint is disabled, we need to manually enable it
                # For Neon specifically, we can't programmatically enable it without API access
                logger.warning("Could not wake up endpoint automatically")
                logger.info("Please enable the endpoint in your database provider's console")
                return False

        except Exception as e:
            logger.error(f"Error in wake_up_endpoint: {str(e)}")
            return False

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
                    connect_args={'connect_timeout': 10}  # Add timeout
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

            # Special handling for endpoint disabled errors
            error_str = str(e).lower()
            if 'endpoint is disabled' in error_str:
                logger.warning("PostgreSQL endpoint is disabled. This is normal for serverless databases after periods of inactivity.")
                # Could trigger notification or auto-restart here
            elif 'connection' in error_str and ('timed out' in error_str or 'refused' in error_str):
                logger.warning("Database connection timed out or was refused. The server may be under high load.")

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

    @staticmethod
    def wake_up_endpoint(uri: str) -> bool:
        """
        Attempt to wake up a disabled database endpoint

        Neon and other serverless PostgreSQL providers automatically shut down
        inactive compute instances. This method will attempt several gentle
        reconnections to wake up the endpoint.
        """
        logger.info("Attempting to wake up database endpoint...")

        # We'll try a few times with increasing delays
        for attempt in range(1, 4):
            try:
                from sqlalchemy import create_engine
                engine = create_engine(
                    uri,
                    pool_pre_ping=True,
                    # Small pool for wake-up attempts
                    pool_size=1,
                    max_overflow=0,
                    # Use a longer timeout for wake-up
                    connect_args={'connect_timeout': 20}
                )

                # Try to establish connection
                with engine.connect() as conn:
                    conn.execute(text('SELECT 1'))

                logger.info(f"Successfully woke up database endpoint on attempt {attempt}")
                return True

            except Exception as e:
                logger.warning(f"Wake-up attempt {attempt} failed: {str(e)}")
                # Exponential backoff with jitter
                delay = (2 ** attempt) + (time.time() % 1)
                time.sleep(delay)

        logger.error("Failed to wake up database endpoint after multiple attempts")
        return False