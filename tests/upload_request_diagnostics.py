"""
Diagnostic tool for analyzing bank statement upload requests
Does not modify any existing functionality
"""
import logging
from flask import request, Blueprint
from werkzeug.utils import secure_filename
import json

# Setup separate logger for diagnostics only
diagnostic_logger = logging.getLogger('upload_diagnostics')
diagnostic_logger.setLevel(logging.DEBUG)
fh = logging.FileHandler('upload_diagnostics.log')
fh.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))
diagnostic_logger.addHandler(fh)

upload_diagnostics = Blueprint('upload_diagnostics', __name__)

@upload_diagnostics.before_request
def log_request_info():
    """Log detailed request information for debugging"""
    try:
        diagnostic_logger.debug("=== New Upload Request ===")
        diagnostic_logger.debug(f"Request Method: {request.method}")
        diagnostic_logger.debug(f"Content Type: {request.content_type}")
        diagnostic_logger.debug(f"Headers: {dict(request.headers)}")
        
        # Log form data if present
        if request.form:
            diagnostic_logger.debug("Form Data:")
            for key in request.form.keys():
                # Don't log CSRF token or sensitive data
                if key != 'csrf_token':
                    diagnostic_logger.debug(f"- {key}: {request.form[key]}")
                else:
                    diagnostic_logger.debug("- csrf_token: [PRESENT]")
        
        # Log file information if present
        if request.files:
            diagnostic_logger.debug("Files:")
            for key in request.files.keys():
                file = request.files[key]
                if file.filename:
                    diagnostic_logger.debug(f"- {key}: {secure_filename(file.filename)}")
                    diagnostic_logger.debug(f"  Content Type: {file.content_type}")
                    diagnostic_logger.debug(f"  Headers: {file.headers}")
    
    except Exception as e:
        diagnostic_logger.error(f"Error logging request: {str(e)}", exc_info=True)

def analyze_upload_error(error):
    """Analyze upload errors without modifying behavior"""
    try:
        diagnostic_logger.error("=== Upload Error Analysis ===")
        diagnostic_logger.error(f"Error Type: {type(error).__name__}")
        diagnostic_logger.error(f"Error Message: {str(error)}")
        
        if hasattr(error, 'code'):
            diagnostic_logger.error(f"Error Code: {error.code}")
        
        if hasattr(error, 'description'):
            diagnostic_logger.error(f"Error Description: {error.description}")
            
        # Log request context if available
        if request:
            diagnostic_logger.error("Request Context:")
            diagnostic_logger.error(f"- Method: {request.method}")
            diagnostic_logger.error(f"- URL: {request.url}")
            diagnostic_logger.error(f"- Headers: {dict(request.headers)}")
            
    except Exception as e:
        diagnostic_logger.error(f"Error in error analysis: {str(e)}", exc_info=True)

def register_diagnostics(app):
    """Register diagnostic routes without affecting main application"""
    app.register_blueprint(upload_diagnostics, url_prefix='/diagnostic')
