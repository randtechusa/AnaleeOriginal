"""
AI-Powered Financial Module Predictive Maintenance System
With comprehensive monitoring of database health and fallback mechanisms
"""
import logging
import gc
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy import func
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from models import db, ErrorLog, Transaction, Account
from utils.db_health import DatabaseHealth

# Import AI service conditionally to handle missing dependencies
try:
    from ai_insights import FinancialInsightsGenerator
    AI_SERVICE_AVAILABLE = True
except ImportError:
    AI_SERVICE_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MaintenanceMonitor:
    """
    Enhanced maintenance monitor with comprehensive health checking
    and improved database fallback support
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.health_metrics = {}
        self.last_check = None
        self.db_health = DatabaseHealth.get_instance()
        self.system_status = "normal"  # normal, degraded, critical
        self.fallback_active = False
        
    def check_system_health(self) -> Dict[str, Any]:
        """
        Comprehensive system health check with enhanced error handling
        """
        try:
            start_time = datetime.utcnow()
            
            # Check database health first - if critical, other checks may fail
            db_health = self._check_database_health()
            self.fallback_active = db_health.get('using_fallback', False)
            
            metrics = {
                'database': db_health,
                'error_rate': self._calculate_error_rate(),
                'performance': self._check_performance_metrics(),
                'resource_usage': self._check_resource_usage(),
                'ai_service': self._check_ai_service_health(),
                'timestamp': start_time,
                'using_fallback': self.fallback_active
            }

            # Determine overall system status
            if db_health.get('status') == 'critical':
                self.system_status = 'critical'
            elif db_health.get('status') == 'degraded':
                self.system_status = 'degraded'
            else:
                self.system_status = 'normal'
                
            metrics['system_status'] = self.system_status

            self.health_metrics = metrics
            self.last_check = start_time

            return metrics
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def _check_database_health(self) -> Dict[str, Any]:
        """
        Enhanced database health check with more comprehensive metrics
        and fallback detection
        """
        try:
            # Get metrics from DatabaseHealth module
            db_metrics = self.db_health.get_health_metrics()
            
            # Determine if using SQLite fallback
            db_uri = ''
            using_fallback = False
            try:
                from flask import current_app
                if current_app:
                    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
                    using_fallback = 'sqlite' in db_uri.lower()
            except:
                pass
                
            # Try a simple database query to verify connection
            connection_status, response_time = self._test_db_connection()
            
            # Determine status with more granularity
            if not connection_status:
                status = 'critical'
            elif db_metrics['consecutive_failures'] > 0 or using_fallback:
                status = 'degraded'
            else:
                status = 'healthy'
                
            return {
                'status': status,
                'response_time': response_time if response_time is not None else db_metrics['avg_response_time'],
                'failover_count': db_metrics['failover_count'],
                'consecutive_failures': db_metrics['consecutive_failures'],
                'using_fallback': using_fallback,
                'db_type': 'sqlite' if using_fallback else 'postgresql',
                'healthy': status == 'healthy',
                'metrics': db_metrics
            }
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            return {
                'status': 'critical',
                'error': str(e),
                'healthy': False
            }
            
    def _test_db_connection(self) -> Tuple[bool, Optional[float]]:
        """Test database connection with a simple query"""
        try:
            import time
            start_time = time.time()
            # Execute a simple database query
            with db.engine.connect() as conn:
                conn.execute("SELECT 1")
            elapsed = time.time() - start_time
            return True, elapsed
        except OperationalError as e:
            logger.warning(f"Database connection test failed: {str(e)}")
            return False, None
        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemy error in connection test: {str(e)}")
            return False, None
        except Exception as e:
            logger.error(f"Unexpected error in database connection test: {str(e)}")
            return False, None

    def _calculate_error_rate(self) -> Dict[str, Any]:
        """
        Calculate system error rates with enhanced error handling
        """
        try:
            hour_ago = datetime.utcnow() - timedelta(hours=1)
            total_errors = ErrorLog.query.filter(
                ErrorLog.timestamp > hour_ago
            ).count()

            error_types = {}
            try:
                type_results = db.session.query(
                    ErrorLog.error_type,
                    func.count(ErrorLog.id)
                ).filter(
                    ErrorLog.timestamp > hour_ago
                ).group_by(ErrorLog.error_type).all()
                
                error_types = dict(type_results)
            except Exception as e:
                logger.warning(f"Error type distribution calculation failed: {str(e)}")

            return {
                'hourly_rate': total_errors,
                'error_distribution': error_types,
                'status': 'critical' if total_errors > 100 else 'warning' if total_errors > 50 else 'normal'
            }
        except Exception as e:
            logger.error(f"Error rate calculation failed: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def _check_performance_metrics(self) -> Dict[str, Any]:
        """
        Check system performance metrics with enhanced error handling
        """
        try:
            hour_ago = datetime.utcnow() - timedelta(hours=1)
            
            # Use safe queries with fallbacks
            transaction_count = 0
            active_accounts = 0
            
            try:
                transaction_count = Transaction.query.filter(
                    Transaction.created_at > hour_ago
                ).count()
            except Exception as e:
                logger.warning(f"Transaction count query failed: {str(e)}")
                
            try:
                active_accounts = Account.query.filter_by(is_active=True).count()
            except Exception as e:
                logger.warning(f"Active accounts query failed: {str(e)}")
            
            metrics = {
                'transaction_count': transaction_count,
                'active_accounts': active_accounts,
                'using_fallback': self.fallback_active
            }
            return metrics
        except Exception as e:
            logger.error(f"Performance check failed: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def _check_resource_usage(self) -> Dict[str, Any]:
        """
        Check system resource usage with safer imports
        """
        try:
            import psutil
            
            # Get CPU usage with a brief delay for accuracy
            cpu = psutil.cpu_percent(interval=0.1)
            
            # Get memory usage
            memory = psutil.virtual_memory()
            
            # Get disk usage safely
            disk_usage = {'percent': 0}
            try:
                disk_usage = psutil.disk_usage('/')
            except Exception as e:
                logger.warning(f"Disk usage check failed: {str(e)}")
            
            return {
                'cpu_percent': cpu,
                'memory_percent': memory.percent,
                'memory_available_mb': memory.available / (1024 * 1024),
                'disk_percent': disk_usage.percent if hasattr(disk_usage, 'percent') else 0,
                'status': 'warning' if cpu > 80 or memory.percent > 80 else 'normal'
            }
        except ImportError:
            return {'status': 'unavailable', 'message': 'psutil not installed'}
        except Exception as e:
            logger.error(f"Resource usage check failed: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def _check_ai_service_health(self) -> Dict[str, Any]:
        """
        Check AI service health with enhanced error handling
        """
        if not AI_SERVICE_AVAILABLE:
            return {
                'healthy': False,
                'status': 'unavailable',
                'message': 'AI service dependencies not available'
            }
            
        try:
            ai_service = FinancialInsightsGenerator()
            health = ai_service.get_service_health()
            return {
                'healthy': health['status'] == 'healthy',
                'status': health['status'],
                'metrics': health
            }
        except Exception as e:
            logger.error(f"AI service health check failed: {str(e)}")
            return {
                'healthy': False,
                'status': 'error',
                'error': str(e)
            }

    def _check_error_logs(self) -> Dict[str, Any]:
        """
        Check recent error logs with improved SQLAlchemy error handling
        """
        try:
            # Use a safer time comparison to avoid timezone issues
            hour_ago = datetime.now() - timedelta(hours=1)
            
            recent_errors = 0
            try:
                recent_errors = ErrorLog.query.filter(
                    ErrorLog.timestamp >= hour_ago
                ).count()
            except Exception as e:
                logger.warning(f"Error log query failed: {str(e)}")
                
            return {
                'healthy': recent_errors < 5,
                'recent_error_count': recent_errors,
                'status': 'critical' if recent_errors > 20 else 'warning' if recent_errors >= 5 else 'normal'
            }
        except Exception as e:
            logger.error(f"Error log check failed: {str(e)}")
            return {
                'healthy': False,
                'error': str(e),
                'status': 'error'
            }

    def predict_maintenance_needs(self) -> List[Dict[str, Any]]:
        """
        Predict maintenance needs based on system metrics with enhanced
        prediction logic and prioritization
        """
        if not self.health_metrics or self.last_check is None or \
           (datetime.utcnow() - self.last_check) > timedelta(minutes=5):
            self.check_system_health()

        predictions = []
        metrics = self.health_metrics

        # Database health predictions with improved criteria
        db_metrics = metrics.get('database', {})
        if db_metrics.get('status') == 'critical':
            predictions.append({
                'component': 'database',
                'priority': 'critical',
                'prediction': 'Database connection failure detected',
                'recommendation': 'Immediate attention required - verify database endpoint availability'
            })
        elif db_metrics.get('status') == 'degraded':
            if db_metrics.get('using_fallback', False):
                predictions.append({
                    'component': 'database',
                    'priority': 'high',
                    'prediction': 'Using SQLite fallback database',
                    'recommendation': 'Investigate and restore PostgreSQL connection when possible'
                })
            else:
                predictions.append({
                    'component': 'database',
                    'priority': 'high',
                    'prediction': 'Database performance degradation detected',
                    'recommendation': 'Schedule maintenance window for database optimization'
                })

        # Error rate predictions with better thresholds
        error_metrics = metrics.get('error_rate', {})
        error_rate = error_metrics.get('hourly_rate', 0)
        if error_rate > 100:
            predictions.append({
                'component': 'application',
                'priority': 'critical',
                'prediction': f'Critical error rate detected: {error_rate} errors/hour',
                'recommendation': 'Immediate investigation required'
            })
        elif error_rate > 50:
            predictions.append({
                'component': 'application',
                'priority': 'high',
                'prediction': f'High error rate detected: {error_rate} errors/hour',
                'recommendation': 'Investigate error patterns and implement fixes'
            })
        elif error_rate > 20:
            predictions.append({
                'component': 'application',
                'priority': 'medium',
                'prediction': f'Elevated error rate: {error_rate} errors/hour',
                'recommendation': 'Monitor error trends and investigate if persisting'
            })

        # Resource usage predictions with improved thresholds
        resource_metrics = metrics.get('resource_usage', {})
        if resource_metrics.get('cpu_percent', 0) > 90:
            predictions.append({
                'component': 'system',
                'priority': 'high',
                'prediction': 'Critical CPU usage detected',
                'recommendation': 'Investigate performance bottlenecks'
            })
        elif resource_metrics.get('memory_percent', 0) > 85:
            predictions.append({
                'component': 'system',
                'priority': 'high',
                'prediction': 'High memory usage detected',
                'recommendation': 'Check for memory leaks or consider scaling resources'
            })
        elif resource_metrics.get('disk_percent', 0) > 90:
            predictions.append({
                'component': 'system',
                'priority': 'high',
                'prediction': 'Disk space nearly full',
                'recommendation': 'Clean up unused files or increase storage capacity'
            })
            
        # AI service health predictions
        ai_metrics = metrics.get('ai_service', {})
        if ai_metrics.get('status') == 'unavailable':
            predictions.append({
                'component': 'ai_service',
                'priority': 'medium',
                'prediction': 'AI service unavailable',
                'recommendation': 'Verify API keys and service dependencies'
            })
        elif ai_metrics.get('status') == 'error':
            predictions.append({
                'component': 'ai_service',
                'priority': 'high',
                'prediction': 'AI service errors detected',
                'recommendation': 'Check error logs and API configuration'
            })

        return predictions

    def get_health_dashboard_data(self) -> Dict[str, Any]:
        """
        Get comprehensive health dashboard data with enhanced
        prediction algorithms and status summary
        """
        self.check_system_health()
        predictions = self.predict_maintenance_needs()
        
        # Determine the highest priority action
        highest_priority = None
        if predictions:
            priorities = {'critical': 3, 'high': 2, 'medium': 1, 'low': 0}
            highest_priority = max(predictions, 
                                  key=lambda x: priorities.get(x.get('priority', 'low'), 0))
            
        return {
            'system_status': self.system_status,
            'metrics': self.health_metrics,
            'predictions': predictions,
            'highest_priority_action': highest_priority,
            'last_update': datetime.utcnow().isoformat(),
            'using_fallback': self.fallback_active
        }
        
    def check_module_health(self, user_id=None) -> Dict[str, Any]:
        """
        Simplified health check interface for system modules
        with improved error handling
        """
        try:
            health_status = {
                'database': self._check_database_health(),
                'ai_service': self._check_ai_service_health(),
                'error_monitoring': self._check_error_logs(),
                'timestamp': datetime.now().isoformat()
            }
            
            # Determine overall system status
            critical_components = [c for c, status in health_status.items() 
                                 if isinstance(status, dict) and status.get('status') == 'critical']
            
            degraded_components = [c for c, status in health_status.items() 
                                 if isinstance(status, dict) and status.get('status') == 'degraded']
            
            if critical_components:
                health_status['system_status'] = 'critical'
                self.system_status = 'critical'
            elif degraded_components:
                health_status['system_status'] = 'degraded'
                self.system_status = 'degraded'
            else:
                health_status['system_status'] = 'normal'
                self.system_status = 'normal'
                
            if health_status['system_status'] != 'normal':
                self.logger.warning(f"System health check indicates {health_status['system_status']} status")
                
            return health_status
        
        except Exception as e:
            self.logger.error(f"Module health check failed: {str(e)}")
            return {
                'system_status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
