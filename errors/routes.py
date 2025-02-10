"""
Error monitoring and status dashboard routes
Handles display and tracking of system errors and AI service status
"""

import logging
from datetime import datetime, timedelta
try:
    from flask import Blueprint, render_template, current_app
    from flask_login import login_required
except ImportError as e:
    logging.error(f"Failed to import Flask modules: {str(e)}")
    raise

import traceback
from . import errors
from models import db
from ai_insights import FinancialInsightsGenerator

# Configure logging
logger = logging.getLogger(__name__)
handler = logging.FileHandler('error_monitoring.log')
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)
logger.setLevel(logging.ERROR)

@errors.route('/dashboard')
@login_required
def error_dashboard():
    """Display error monitoring dashboard with AI service status"""
    try:
        # Get AI service status
        ai_service = FinancialInsightsGenerator()
        ai_status = {
            'consecutive_failures': 0,
            'error_count': 0,
            'last_success': None,
            'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        try:
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
        except AttributeError as e:
            logger.warning(f"Error accessing AI service status attributes: {str(e)}")

        # Get recent errors from logs with proper error handling
        recent_errors = []
        try:
            service_status = getattr(ai_service, 'service_status', None)
            if service_status and hasattr(service_status, 'last_error'):
                error_data = service_status.last_error
                if isinstance(error_data, dict):
                    recent_errors.append({
                        'timestamp': error_data.get('timestamp', datetime.now()).strftime('%Y-%m-%d %H:%M:%S'),
                        'type': error_data.get('error_type', 'Unknown Error'),
                        'message': error_data.get('message', 'No error message available')
                    })

            # Add initialization error if present
            if hasattr(ai_service, 'client_error'):
                recent_errors.append({
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'type': 'AI Service Initialization Error',
                    'message': str(ai_service.client_error)
                })
        except Exception as e:
            logger.error(f"Error retrieving error history: {str(e)}\n{traceback.format_exc()}")
            recent_errors.append({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'type': 'Error Log Access Error',
                'message': 'Unable to retrieve complete error history'
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

        # Calculate service health metrics with error handling
        try:
            total_ops = max(1, ai_status['error_count'] + (1 if ai_status['last_success'] else 0))
            success_rate = ((total_ops - ai_status['error_count']) / total_ops) * 100
            uptime = f"{success_rate:.1f}% success rate"
        except Exception as e:
            logger.error(f"Error calculating health metrics: {str(e)}")
            uptime = "Unable to calculate uptime"

        return render_template('error_dashboard.html',
                             ai_status=ai_status,
                             recent_errors=recent_errors,
                             recommendations=recommendations,
                             uptime=uptime)

    except Exception as e:
        logger.error(f"Error loading error dashboard: {str(e)}\n{traceback.format_exc()}")
        return render_template('error_dashboard.html', 
                             error="Error loading dashboard data",
                             ai_status={'error_count': 0, 'consecutive_failures': 0},
                             recent_errors=[{
                                 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                 'type': 'Dashboard Error',
                                 'message': str(e)
                             }],
                             recommendations=["System encountered an error, please try again later"],
                             uptime="Unknown")