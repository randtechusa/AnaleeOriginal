"""
Audit Service: Provides system-wide audit logging capabilities
"""
from typing import Optional, Any, Dict, List
from datetime import datetime
import json
import logging
import threading
import inspect
from functools import wraps
from flask import request, has_request_context, current_app
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

class AuditService:
    """Centralized service for audit logging with advanced features"""
    _instance = None
    _buffer = []
    _buffer_lock = threading.RLock()
    _disabled = False
    _db = None
    _app = None
    _buffer_size = 10  # Max buffer size before flushing

    def __new__(cls, *args, **kwargs):
        """Singleton pattern implementation"""
        if cls._instance is None:
            cls._instance = super(AuditService, cls).__new__(cls)
        return cls._instance

    def __init__(self, db=None):
        """Initialize the audit service"""
        if db:
            self._db = db

    def init_app(self, app):
        """Initialize with Flask app and database"""
        self._app = app
        
        # Get database instance if not provided in constructor
        if not self._db:
            from extensions import db
            self._db = db
        
        # Configure buffer size from app config
        if app.config.get('AUDIT_BUFFER_SIZE'):
            self._buffer_size = app.config.get('AUDIT_BUFFER_SIZE')
        
        # Register teardown handler
        app.teardown_appcontext(self._teardown)

    def _teardown(self, exception):
        """Flush buffer on app context teardown"""
        self.flush_buffer()

    def disable(self):
        """Temporarily disable audit logging"""
        self._disabled = True

    def enable(self):
        """Re-enable audit logging"""
        self._disabled = False

    def log_activity(self, 
                    user_id: Optional[int], 
                    action: str, 
                    resource_type: str, 
                    resource_id: Optional[Any] = None,
                    description: Optional[str] = None,
                    ip_address: Optional[str] = None,
                    user_agent: Optional[str] = None,
                    status: str = 'success',
                    additional_data: Optional[Dict] = None) -> bool:
        """
        Log an activity for audit purposes
        
        Args:
            user_id: ID of the user performing the action
            action: Type of action (create, update, delete, etc.)
            resource_type: Type of resource being acted upon
            resource_id: ID of the resource being acted upon
            description: Optional detailed description
            ip_address: Optional IP address of the user
            user_agent: Optional user agent string
            status: Status of the action (success, failure, etc.)
            additional_data: Optional additional structured data
            
        Returns:
            bool: True if log was successful, False otherwise
        """
        # Skip if disabled
        if self._disabled:
            return False
        
        # Auto-populate request data if in request context
        if has_request_context() and not ip_address:
            ip_address = request.remote_addr
            user_agent = request.user_agent.string if not user_agent else user_agent
        
        # Auto-populate user if available from flask-login and not explicitly provided
        if has_request_context() and user_id is None and current_user.is_authenticated:
            user_id = current_user.id
        
        # Convert resource_id to string if it's not None
        if resource_id is not None:
            resource_id = str(resource_id)
        
        # Prepare clean additional data
        clean_additional_data = None
        if additional_data:
            clean_additional_data = json.dumps(self._sanitize_data(additional_data))
        
        # Create log entry dictionary
        log_entry = {
            'user_id': user_id,
            'action': action,
            'resource_type': resource_type,
            'resource_id': resource_id,
            'description': description,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'status': status,
            'additional_data': clean_additional_data,
        }
        
        # Add to buffer
        with self._buffer_lock:
            self._buffer.append(log_entry)
            
            # Auto-flush if buffer reaches threshold
            if len(self._buffer) >= self._buffer_size:
                return self.flush_buffer()
        
        return True

    def _sanitize_data(self, data: Dict) -> Dict:
        """Remove sensitive information from data"""
        if not data:
            return {}
        
        # Create a copy to avoid modifying the original
        sanitized = data.copy()
        
        # List of sensitive fields to remove
        sensitive_fields = [
            'password', 'password_hash', 'token', 'secret', 'api_key', 
            'access_token', 'refresh_token', 'private_key', 'credential'
        ]
        
        # Remove sensitive fields
        for field in sensitive_fields:
            if field in sanitized:
                sanitized[field] = '[REDACTED]'
        
        # Recursively sanitize nested dictionaries
        for key, value in sanitized.items():
            if isinstance(value, dict):
                sanitized[key] = self._sanitize_data(value)
        
        return sanitized

    def _write_to_db(self, log_entry: Dict) -> bool:
        """Write a log entry to the database"""
        try:
            # Import here to avoid circular imports
            from models import AuditLog, db
            
            # Create new audit log record
            log = AuditLog(**log_entry)
            db.session.add(log)
            db.session.commit()
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error writing audit log to database: {str(e)}")
            if current_app:
                current_app.logger.error(f"Error writing audit log to database: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error writing audit log: {str(e)}")
            if current_app:
                current_app.logger.error(f"Unexpected error writing audit log: {str(e)}")
            return False

    def flush_buffer(self) -> bool:
        """Flush buffered log entries to the database"""
        if not self._buffer:
            return True
        
        success = True
        with self._buffer_lock:
            buffer_copy = self._buffer.copy()
            self._buffer.clear()
        
        for log_entry in buffer_copy:
            if not self._write_to_db(log_entry):
                success = False
                # If write fails, add back to buffer
                with self._buffer_lock:
                    self._buffer.append(log_entry)
        
        return success

    def auditable(self, resource_type, action=None):
        """
        Decorator to automatically audit a function call
        
        Args:
            resource_type: Type of resource being acted upon
            action: Optional override for action name (default: function name)
            
        Example:
            @audit_service.auditable('user', 'create')
            def create_user(username, email):
                # Function body
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Get function name if action not specified
                func_action = action or func.__name__
                
                # Extract resource_id from args or kwargs if possible
                resource_id = None
                func_args = inspect.getfullargspec(func).args
                if len(args) > 1 and 'id' in func_args:
                    id_index = func_args.index('id')
                    if id_index < len(args):
                        resource_id = args[id_index]
                elif 'id' in kwargs:
                    resource_id = kwargs['id']
                
                # Log the action start
                self.log_activity(
                    user_id=current_user.id if has_request_context() and current_user.is_authenticated else None,
                    action=f"{func_action}_start",
                    resource_type=resource_type,
                    resource_id=resource_id,
                    description=f"Started {func_action} on {resource_type}"
                )
                
                try:
                    # Execute the function
                    result = func(*args, **kwargs)
                    
                    # Log successful completion
                    self.log_activity(
                        user_id=current_user.id if has_request_context() and current_user.is_authenticated else None,
                        action=func_action,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        description=f"Completed {func_action} on {resource_type}",
                        status='success'
                    )
                    
                    return result
                except Exception as e:
                    # Log failure
                    self.log_activity(
                        user_id=current_user.id if has_request_context() and current_user.is_authenticated else None,
                        action=func_action,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        description=f"Failed {func_action} on {resource_type}: {str(e)}",
                        status='failure',
                        additional_data={'error': str(e), 'error_type': type(e).__name__}
                    )
                    # Re-raise the exception
                    raise
            
            return wrapper
        return decorator

# Singleton instance
audit_service = AuditService()

# Convenience functions for easier usage
def log_activity(action, resource_type, resource_id=None, description=None, additional_data=None):
    """Shorthand function to log activity"""
    user_id = current_user.id if has_request_context() and current_user.is_authenticated else None
    return audit_service.log_activity(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        description=description,
        additional_data=additional_data
    )

def auditable(resource_type, action=None):
    """Shorthand decorator to make a function auditable"""
    return audit_service.auditable(resource_type, action)