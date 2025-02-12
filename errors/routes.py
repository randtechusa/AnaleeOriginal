"""
Error monitoring and status dashboard routes
Handles display and tracking of system errors and AI service status with enhanced monitoring
"""

import logging
from datetime import datetime, timedelta
from flask import Blueprint, render_template, current_app, request
from flask_login import login_required
from markupsafe import escape
import traceback
from models import db
from ai_insights import FinancialInsightsGenerator
from threading import Lock
from sqlalchemy import func
from maintenance_monitor import MaintenanceMonitor

# Configure logging with more detailed formatting
logger = logging.getLogger(__name__)
handler = logging.FileHandler('error_monitoring.log')
handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
))
logger.addHandler(handler)
logger.setLevel(logging.ERROR)

# Add thread safety for AI service status access
ai_status_lock = Lock()

bp = Blueprint('errors', __name__)

# Error handlers with enhanced logging
def handle_404_error(error):
    """Handle 404 Not Found errors with contextual information"""
    logger.warning(f"404 error: {error}\nPath: {request.path}\nMethod: {request.method}")
    return render_template('errors/404.html'), 404

def handle_500_error(error):
    """Handle 500 Internal Server errors with detailed logging"""
    logger.error(
        f"500 error: {error}\n"
        f"Path: {request.path}\n"
        f"Method: {request.method}\n"
        f"Client IP: {request.remote_addr}\n"
        f"Traceback:\n{traceback.format_exc()}"
    )
    return render_template('errors/500.html'), 500

def init_error_handlers(bp):
    """Initialize error handlers for the blueprint"""
    bp.register_error_handler(404, handle_404_error)
    bp.register_error_handler(500, handle_500_error)

@bp.route('/dashboard')
@login_required
def error_dashboard():
    """
    Enhanced error monitoring dashboard with AI service status, system health,
    and error pattern analysis
    """
    try:
        # Initialize maintenance monitor for system health checks
        monitor = MaintenanceMonitor()
        system_health = monitor.check_module_health(current_user.id)

        # Initialize default status
        ai_status = {
            'consecutive_failures': 0,
            'error_count': 0,
            'last_success': None,
            'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        recent_errors = []
        error_patterns = []
        system_metrics = {}
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
                                'message': escape(error_data.get('message', 'No error message available')),
                                'module': escape(error_data.get('module', 'Unknown')),
                                'severity': error_data.get('severity', 'medium')
                            })

                    # Add initialization error if present
                    if hasattr(ai_service, 'client_error'):
                        recent_errors.append({
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'type': 'AI Service Initialization Error',
                            'message': escape(str(ai_service.client_error)),
                            'module': 'AI Service',
                            'severity': 'high'
                        })

                # Calculate service health metrics
                total_ops = max(1, ai_status['error_count'] + (1 if ai_status['last_success'] else 0))
                success_rate = ((total_ops - ai_status['error_count']) / total_ops) * 100
                uptime = f"{success_rate:.1f}% success rate"

                # Analyze error patterns (last 24 hours)
                error_patterns = analyze_error_patterns()

                # Get system performance metrics
                system_metrics = get_system_metrics()

            except AttributeError as e:
                logger.warning(f"Error accessing AI service status attributes: {str(e)}")
                recent_errors.append({
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'type': 'Service Status Error',
                    'message': escape(str(e)),
                    'module': 'System Monitor',
                    'severity': 'medium'
                })

        # Generate recommendations based on status
        recommendations = generate_recommendations(ai_status, system_health, error_patterns)

        return render_template('error_dashboard.html',
                            ai_status=ai_status,
                            recent_errors=recent_errors,
                            recommendations=recommendations,
                            uptime=uptime,
                            system_health=system_health,
                            error_patterns=error_patterns,
                            system_metrics=system_metrics)

    except Exception as e:
        logger.error(f"Error loading error dashboard: {str(e)}\n{traceback.format_exc()}")
        return render_template('error_dashboard.html', 
                            error=escape(str(e)),
                            ai_status={'error_count': 0, 'consecutive_failures': 0},
                            recent_errors=[{
                                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'type': 'Dashboard Error',
                                'message': escape(str(e)),
                                'module': 'Error Dashboard',
                                'severity': 'high'
                            }],
                            recommendations=["System encountered an error, please try again later"],
                            uptime="Unknown")

def analyze_error_patterns():
    """Analyze patterns in recent errors"""
    try:
        # Get errors from the last 24 hours
        yesterday = datetime.now() - timedelta(days=1)

        # Read and parse error log file
        patterns = []
        error_counts = {}

        with open('error_monitoring.log', 'r') as log_file:
            for line in log_file:
                try:
                    # Parse log entry
                    if ' ERROR ' in line:
                        error_type = line.split(' - ')[-1].strip()
                        error_counts[error_type] = error_counts.get(error_type, 0) + 1
                except:
                    continue

        # Identify patterns
        for error_type, count in error_counts.items():
            if count > 3:  # Pattern threshold
                patterns.append({
                    'type': error_type,
                    'count': count,
                    'frequency': f"{count} times in 24h",
                    'severity': 'high' if count > 10 else 'medium'
                })

        return sorted(patterns, key=lambda x: x['count'], reverse=True)
    except Exception as e:
        logger.error(f"Error analyzing patterns: {str(e)}")
        return []

def get_system_metrics():
    """Get system performance metrics"""
    try:
        return {
            'response_time': get_average_response_time(),
            'error_rate': calculate_error_rate(),
            'system_load': get_system_load(),
            'memory_usage': get_memory_usage()
        }
    except Exception as e:
        logger.error(f"Error getting system metrics: {str(e)}")
        return {}

def generate_recommendations(ai_status, system_health, error_patterns):
    """Generate intelligent recommendations based on system status"""
    recommendations = []

    # AI service recommendations
    if ai_status['consecutive_failures'] > 3:
        recommendations.extend([
            "AI service experiencing multiple failures - verify API configuration",
            "Check system logs for detailed error messages",
            "Consider refreshing API credentials if issues persist"
        ])
    elif ai_status['consecutive_failures'] > 0:
        recommendations.append("Monitor AI service performance for continued issues")

    # System health recommendations
    for module, health in system_health.items():
        if health.get('status') == 'error':
            recommendations.append(f"Critical: {module} module requires immediate attention")
        elif health.get('status') == 'warning':
            recommendations.append(f"Warning: {module} module showing degraded performance")

    # Error pattern recommendations
    for pattern in error_patterns:
        if pattern['count'] > 10:
            recommendations.append(
                f"Critical: {pattern['type']} occurred {pattern['count']} times - "
                "requires immediate investigation"
            )

    return recommendations

def get_average_response_time():
    """Calculate average response time"""
    try:
        return 500  # Placeholder - implement actual monitoring
    except Exception as e:
        logger.error(f"Error calculating response time: {str(e)}")
        return 0

def calculate_error_rate():
    """Calculate current error rate"""
    try:
        return 0.05  # Placeholder - implement actual calculation
    except Exception as e:
        logger.error(f"Error calculating error rate: {str(e)}")
        return 0

def get_system_load():
    """Get current system load"""
    try:
        return 0.7  # Placeholder - implement actual monitoring
    except Exception as e:
        logger.error(f"Error getting system load: {str(e)}")
        return 0

def get_memory_usage():
    """Get current memory usage"""
    try:
        return 0.6  # Placeholder - implement actual monitoring
    except Exception as e:
        logger.error(f"Error getting memory usage: {str(e)}")
        return 0

init_error_handlers(bp)