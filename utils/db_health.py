"""Database health monitoring and management utilities"""
import logging
import time
import os
from typing import Tuple, Optional, Dict
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError, OperationalError

logger = logging.getLogger(__name__)
handler = logging.FileHandler('database.log')
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

class DatabaseHealth:
    """Singleton class to monitor and manage database health"""
    _instance = None
    
    # Health metrics for tracking status over time
    _health_metrics = {
        'last_check': None,
        'consecutive_failures': 0,
        'total_checks': 0,
        'avg_response_time': 0,
        'total_failures': 0,
        'failover_count': 0,
        'last_failover': None
    }
    
    # Configuration 
    max_failures_before_failover = 3
    check_interval = 60  # seconds

    @classmethod
    def get_instance(cls):
        """Get or create the singleton instance"""
        if cls._instance is None:
            cls._instance = DatabaseHealth()
        return cls._instance

    def __init__(self):
        """Initialize with default values"""
        pass  # All state is kept in class variables for the singleton

    def check_connection(self, uri: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Check database connection health
        
        Args:
            uri: Optional database URI to check. If None, uses the current application's database.
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            start_time = time.time()
            
            if uri:
                # Check specific URI
                engine = create_engine(uri, 
                    pool_pre_ping=True,
                    pool_recycle=3600,
                    connect_args={'connect_timeout': 10}
                )
                with engine.connect() as conn:
                    conn.execute(text('SELECT 1'))
            else:
                # Check current application database
                if not current_app:
                    logger.warning("No Flask app context available for DB health check")
                    return False, "No application context"
                
                engine = current_app.extensions['sqlalchemy'].db.engine
                with engine.connect() as conn:
                    conn.execute(text('SELECT 1'))
            
            # Update metrics on success
            elapsed = time.time() - start_time
            self._update_metrics(elapsed, success=True)
            return True, None
            
        except SQLAlchemyError as e:
            error_msg = f"Database health check failed: {str(e)}"
            
            # Special handling for endpoint disabled errors
            error_str = str(e).lower()
            if 'endpoint is disabled' in error_str:
                logger.warning("PostgreSQL endpoint is disabled. This is normal for serverless databases after periods of inactivity.")
            elif 'connection' in error_str and ('timed out' in error_str or 'refused' in error_str):
                logger.warning("Database connection timed out or was refused. The server may be under high load.")
            
            logger.error(error_msg)
            self._update_metrics(0, success=False)
            return False, error_msg

    def _update_metrics(self, elapsed: float, success: bool):
        """Update health metrics based on check results"""
        metrics = self._health_metrics
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

    def should_failover(self) -> bool:
        """Determine if failover should be triggered based on health metrics"""
        metrics = self._health_metrics
        time_threshold = timedelta(minutes=5)
        
        return (
            metrics['consecutive_failures'] >= self.max_failures_before_failover or
            (metrics['last_check'] and datetime.now() - metrics['last_check'] > time_threshold) or
            (metrics['last_failover'] and 
             datetime.now() - metrics['last_failover'] > timedelta(hours=1) and
             metrics['consecutive_failures'] > 0)
        )

    def perform_failover(self) -> Tuple[bool, Optional[str]]:
        """
        Execute database failover procedure to SQLite
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            logger.warning("Initiating database failover to SQLite")
            metrics = self._health_metrics
            
            # Get current database URI
            if not current_app:
                return False, "No application context for failover"
                
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
            
            # Update metrics
            metrics['failover_count'] += 1
            metrics['last_failover'] = datetime.now()
            
            logger.info("Failover to SQLite complete")
            return True, None
            
        except Exception as e:
            error_msg = f"Failover failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def get_health_metrics(self) -> Dict:
        """Get current health metrics for monitoring"""
        metrics = self._health_metrics.copy()
        metrics['status'] = 'healthy' if metrics['consecutive_failures'] == 0 else 'degraded'
        return metrics

    def wake_up_endpoint(self, uri: str) -> bool:
        """
        Attempt to wake up a disabled database endpoint
        
        Neon and other serverless PostgreSQL providers automatically shut down
        inactive compute instances. This method will attempt several gentle
        reconnections to wake up the endpoint.
        
        Args:
            uri: Database URI to connect to
            
        Returns:
            bool: True if wakeup was successful
        """
        logger.info("Attempting to wake up database endpoint...")
        
        if not uri or 'neon.tech' not in uri.lower():
            logger.info("Not a Neon database or no URL provided")
            return False
            
        # We'll try a few times with increasing delays
        for attempt in range(1, 4):
            try:
                # Construct engine with minimal settings for connection attempt
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