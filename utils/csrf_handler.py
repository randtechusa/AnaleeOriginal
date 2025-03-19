"""
Custom CSRF handling middleware for Flask applications
Provides enhanced CSRF protection with better session handling
"""
import logging
import secrets
from functools import wraps
from flask import request, session, abort, current_app

# Configure logging
logger = logging.getLogger(__name__)

def generate_csrf_token():
    """Generate a secure CSRF token"""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']

def validate_csrf_token(token):
    """Validate a CSRF token against the session token"""
    if token is None or 'csrf_token' not in session:
        logger.warning("CSRF validation failed: Token missing")
        return False
    
    session_token = session.get('csrf_token')
    if not session_token:
        logger.warning("CSRF validation failed: Session token missing")
        return False
    
    # Add debug logging
    if token != session_token:
        logger.warning(f"CSRF token mismatch: {token[:10]}... != {session_token[:10]}...")
        return False
    
    return True

def csrf_protect(view_function):
    """Decorator to protect a view function with CSRF validation"""
    @wraps(view_function)
    def decorated_function(*args, **kwargs):
        # Only check POST/PUT/PATCH/DELETE requests
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            token = request.form.get('csrf_token')
            if not validate_csrf_token(token):
                logger.error("CSRF validation failed")
                abort(400, "The CSRF session token is missing or invalid.")
        return view_function(*args, **kwargs)
    
    return decorated_function

def init_csrf(app):
    """Initialize CSRF protection for the app"""
    # Make generate_csrf_token available in templates
    app.jinja_env.globals['csrf_token'] = generate_csrf_token
    
    # Apply CSRF protection to all routes unless explicitly exempted
    @app.before_request
    def csrf_check():
        # Skip CSRF check for exempted views
        if getattr(request.endpoint, '_csrf_exempt', False):
            return
        
        # Only check for POST/PUT/PATCH/DELETE
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            token = request.form.get('csrf_token')
            if not validate_csrf_token(token):
                logger.error(f"CSRF validation failed for {request.endpoint}")
                abort(400, "The CSRF session token is missing or invalid.")

def csrf_exempt(view_function):
    """Mark a view function as exempt from CSRF protection"""
    view_function._csrf_exempt = True
    return view_function