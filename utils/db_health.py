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
        Check database connection health with enhanced diagnostics
        
        Args:
            uri: Optional database URI to check. If None, uses the current application's database.
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            start_time = time.time()
            
            if uri:
                # Check specific URI
                # Check database type for specialized handling
                is_neon_db = 'neon.tech' in uri.lower()
                is_postgresql = 'postgresql' in uri.lower()
                is_sqlite = 'sqlite' in uri.lower()
                
                # Log database type for diagnostics
                db_type = "SQLite" if is_sqlite else "PostgreSQL (Neon)" if is_neon_db else "PostgreSQL" if is_postgresql else "Unknown"
                logger.info(f"Checking connection to {db_type} database")
                
                # Set engine parameters based on database type
                engine_opts = {
                    'pool_pre_ping': True,
                    'pool_recycle': 3600,
                    'pool_size': 1,
                    'max_overflow': 0
                }
                
                # Add PostgreSQL-specific options
                if is_postgresql:
                    engine_opts['connect_args'] = {'connect_timeout': 10}
                
                engine = create_engine(uri, **engine_opts)
                
                # If it's a Neon database, log endpoint info
                if is_neon_db:
                    try:
                        from urllib.parse import urlparse
                        parsed_uri = urlparse(uri)
                        endpoint_host = parsed_uri.hostname
                        if endpoint_host:  # Check if hostname is not None
                            endpoint_id = endpoint_host.split('.')[0]  # First part may contain endpoint ID
                        else:
                            endpoint_id = "unknown"
                        logger.info(f"Neon database endpoint ID: {endpoint_id}")
                    except Exception as e:
                        logger.warning(f"Error parsing Neon endpoint info: {str(e)}")
                
                with engine.connect() as conn:
                    conn.execute(text('SELECT 1'))
            else:
                # Check current application database
                if not current_app:
                    logger.warning("No Flask app context available for DB health check")
                    return False, "No application context"
                
                # Get database URI from application config for diagnostic purposes
                db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', 'Unknown')
                is_sqlite = 'sqlite' in db_uri.lower()
                db_type = "SQLite" if is_sqlite else "PostgreSQL" if 'postgresql' in db_uri.lower() else "Unknown"
                logger.info(f"Checking connection to application's {db_type} database")
                
                engine = current_app.extensions['sqlalchemy'].db.engine
                with engine.connect() as conn:
                    conn.execute(text('SELECT 1'))
            
            # Update metrics on success
            elapsed = time.time() - start_time
            self._update_metrics(elapsed, success=True)
            return True, None
            
        except SQLAlchemyError as e:
            error_str = str(e).lower()
            error_msg = f"Database health check failed: {str(e)}"
            
            # Enhanced error diagnosis with more specific patterns and advice
            if 'endpoint is disabled' in error_str:
                logger.warning("PostgreSQL endpoint is disabled. This is normal for serverless databases after periods of inactivity.")
                error_msg = "PostgreSQL endpoint is disabled and needs to be woken up. This is normal for serverless databases."
            elif 'timeout' in error_str:
                logger.warning("Database connection timed out - server may be under high load or network issues")
                error_msg = "Database connection timed out. The server may be under high load or experiencing network issues."
            elif 'connection' in error_str and 'refused' in error_str:
                logger.warning("Database connection refused - server may be down or firewall issue")
                error_msg = "Database connection refused. The server may be down or there could be a firewall issue."
            elif 'authentication' in error_str:
                logger.warning("Database authentication failed - credentials may be incorrect")
                error_msg = "Database authentication failed. Credentials may be incorrect or expired."
            elif 'does not exist' in error_str:
                logger.warning("Database or schema does not exist - check database name and availability")
                error_msg = "Database or schema does not exist. Check database name and availability."
            elif 'too many connections' in error_str:
                logger.warning("Too many connections to database - connection pool exhausted")
                error_msg = "Too many connections to database. The connection pool may be exhausted."
            
            logger.error(error_msg)
            self._update_metrics(0, success=False)
            return False, error_msg
        
        except Exception as e:
            # Handle non-SQLAlchemy errors
            error_msg = f"Unexpected error during database health check: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Error type: {type(e).__name__}")
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
        
        if not uri:
            logger.info("No database URI provided")
            return False
            
        # Check if this is a Neon database that might need special handling
        is_neon_db = 'neon.tech' in uri.lower()
        is_postgresql = 'postgresql' in uri.lower()
        
        if not (is_neon_db or is_postgresql):
            logger.info("Not a PostgreSQL database - no wake-up needed")
            return False
            
        # For Neon databases, try to contact their API to wake up the endpoint (if possible)
        if is_neon_db:
            # Extract the endpoint ID from the URI (for potential future API integration)
            try:
                from urllib.parse import urlparse
                parsed_uri = urlparse(uri)
                endpoint_host = parsed_uri.hostname
                endpoint_id = endpoint_host.split('.')[0]  # First part may contain endpoint ID
                
                logger.info(f"Detected Neon database endpoint: {endpoint_id}")
                
                # In the future, we could contact the Neon API here to enable the endpoint
                # For now, just log the detection
            except Exception as e:
                logger.warning(f"Error parsing Neon endpoint info: {str(e)}")
        
        # Enhanced wake-up procedure with better error handling and diagnostics
        for attempt in range(1, 4):
            try:
                # For PostgreSQL connections, use psycopg2 directly with better diagnostics
                if is_postgresql:
                    try:
                        # Parse the URI to extract components for direct connection
                        from urllib.parse import urlparse
                        parsed_uri = urlparse(uri)
                        db_name = parsed_uri.path.lstrip('/')
                        host = parsed_uri.hostname
                        port = parsed_uri.port or 5432
                        username = parsed_uri.username
                        password = parsed_uri.password
                        
                        import psycopg2
                        conn = psycopg2.connect(
                            dbname=db_name,
                            user=username,
                            password=password,
                            host=host,
                            port=port,
                            connect_timeout=30  # Longer timeout for wake-up
                        )
                        conn.close()
                        logger.info(f"Successfully woke up PostgreSQL endpoint on attempt {attempt}")
                        return True
                    except psycopg2.OperationalError as e:
                        error_str = str(e).lower()
                        if 'endpoint is disabled' in error_str:
                            logger.warning(f"Neon endpoint explicitly reported as disabled - attempt {attempt}")
                            if attempt == 3:
                                logger.error("Neon endpoint remains disabled after multiple attempts")
                                return False
                        raise  # Re-raise for the outer exception handler
                
                # Fallback to SQLAlchemy connection
                engine_opts = {
                    'pool_pre_ping': True,
                    'pool_size': 1,
                    'max_overflow': 0,
                }
                
                if is_postgresql:
                    engine_opts['connect_args'] = {'connect_timeout': 30}
                
                engine = create_engine(uri, **engine_opts)
                
                # Try to establish connection
                with engine.connect() as conn:
                    conn.execute(text('SELECT 1'))
                
                logger.info(f"Successfully woke up database endpoint on attempt {attempt}")
                return True
                
            except Exception as e:
                error_str = str(e).lower()
                
                # Check for specific errors that would indicate the endpoint is offline
                if is_neon_db and 'endpoint is disabled' in error_str:
                    logger.warning(f"Neon endpoint reported as disabled on attempt {attempt}")
                elif 'timeout' in error_str:
                    logger.warning(f"Connection timeout on attempt {attempt}")
                elif 'refused' in error_str:
                    logger.warning(f"Connection refused on attempt {attempt}")
                else:
                    logger.warning(f"Wake-up attempt {attempt} failed: {str(e)}")
                
                # Exponential backoff with jitter
                delay = (2 ** attempt) + (time.time() % 1)
                logger.info(f"Waiting {delay:.2f} seconds before next attempt...")
                time.sleep(delay)
        
        logger.error("Failed to wake up database endpoint after multiple attempts")
        return False