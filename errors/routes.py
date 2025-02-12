"""
Error monitoring and status dashboard routes
Handles display and tracking of system errors and AI service status
"""

import logging
from datetime import datetime, timedelta
from flask import Blueprint, render_template, current_app
from flask_login import login_required
from markupsafe import escape
import traceback
from models import db
from ai_insights import FinancialInsightsGenerator
from threading import Lock

# Configure logging
logger = logging.getLogger(__name__)
handler = logging.FileHandler('error_monitoring.log')
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)
logger.setLevel(logging.ERROR)

# Add thread safety for AI service status access
ai_status_lock = Lock()

bp = Blueprint('errors', __name__)

# Error handlers
def handle_404_error(error):
    """Handle 404 Not Found errors"""
    logger.warning(f"404 error: {error}")
    return render_template('errors/404.html'), 404

def handle_500_error(error):
    """Handle 500 Internal Server errors"""
    logger.error(f"500 error: {error}\n{traceback.format_exc()}")
    return render_template('errors/500.html'), 500

def init_error_handlers(bp):
    """Initialize error handlers for the blueprint"""
    bp.register_error_handler(404, handle_404_error)
    bp.register_error_handler(500, handle_500_error)

@bp.route('/dashboard')
@login_required
def error_dashboard():
    """Display error monitoring dashboard with AI service status"""
    try:
        # Initialize default status
        ai_status = {
            'consecutive_failures': 0,
            'error_count': 0,
            'last_success': None,
            'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        recent_errors = []
        uptime = "Unknown"

        with ai_status_lock:
            try:
                # Get AI service status
                ai_service = FinancialInsightsGenerator()

                # Safely access AI service status attributes
                service_status = getattr(ai_service, 'service_status', None)
                if service_status:
                    ai_status.update({
                        'consecutive_failures': getattr(service_status, 'consecutive_failures', 0),
                        'error_count': getattr(service_status, 'error_count', 0),
                        'last_success': (service_status.last_success.strftime('%Y-%m-%d %H:%M:%S') 
                                      if hasattr(service_status, 'last_success') and 
                                      service_status.last_success else None),
                    })

                    # Get recent errors from logs with proper error handling
                    if hasattr(service_status, 'last_error'):
                        error_data = service_status.last_error
                        if isinstance(error_data, dict):
                            recent_errors.append({
                                'timestamp': error_data.get('timestamp', datetime.now()).strftime('%Y-%m-%d %H:%M:%S'),
                                'type': escape(error_data.get('error_type', 'Unknown Error')),
                                'message': escape(error_data.get('message', 'No error message available'))
                            })

                    # Add initialization error if present
                    if hasattr(ai_service, 'client_error'):
                        recent_errors.append({
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'type': 'AI Service Initialization Error',
                            'message': escape(str(ai_service.client_error))
                        })

                # Calculate service health metrics
                total_ops = max(1, ai_status['error_count'] + (1 if ai_status['last_success'] else 0))
                success_rate = ((total_ops - ai_status['error_count']) / total_ops) * 100
                uptime = f"{success_rate:.1f}% success rate"

            except AttributeError as e:
                logger.warning(f"Error accessing AI service status attributes: {str(e)}")
                recent_errors.append({
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'type': 'Service Status Error',
                    'message': escape(str(e))
                })

        # Generate recommendations based on status
        recommendations = []
        failure_count = ai_status['consecutive_failures']

        if failure_count > 3:
            recommendations.extend([
                "AI service experiencing multiple failures - verify API configuration",
                "Check system logs for detailed error messages",
                "Consider refreshing API credentials if issues persist"
            ])
        elif failure_count > 0:
            recommendations.append("Monitor AI service performance for continued issues")

        # Add OpenAI specific recommendations
        if any('OpenAI' in err.get('message', '') for err in recent_errors):
            recommendations.append("Verify OpenAI API configuration and credentials")

        return render_template('error_dashboard.html',
                             ai_status=ai_status,
                             recent_errors=recent_errors,
                             recommendations=recommendations,
                             uptime=uptime)

    except Exception as e:
        logger.error(f"Error loading error dashboard: {str(e)}\n{traceback.format_exc()}")
        return render_template('error_dashboard.html', 
                             error=escape(str(e)),
                             ai_status={'error_count': 0, 'consecutive_failures': 0},
                             recent_errors=[{
                                 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                 'type': 'Dashboard Error',
                                 'message': escape(str(e))
                             }],
                             recommendations=["System encountered an error, please try again later"],
                             uptime="Unknown")

init_error_handlers(bp)