"""
AI-Powered Financial Module Predictive Maintenance System
"""
import logging
import gc
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy import func
from models import db, ErrorLog, Transaction, Account
from utils.db_health import DatabaseHealth

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MaintenanceMonitor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.health_metrics = {}
        self.last_check = None
        self.db_health = DatabaseHealth.get_instance()

    def check_system_health(self) -> Dict:
        """Comprehensive system health check"""
        try:
            start_time = datetime.utcnow()
            metrics = {
                'database': self._check_database_health(),
                'error_rate': self._calculate_error_rate(),
                'performance': self._check_performance_metrics(),
                'resource_usage': self._check_resource_usage(),
                'timestamp': start_time
            }

            self.health_metrics = metrics
            self.last_check = start_time

            return metrics
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def _check_database_health(self) -> Dict:
        """Check database health status"""
        db_metrics = self.db_health.get_health_metrics()
        return {
            'status': 'healthy' if db_metrics['consecutive_failures'] == 0 else 'degraded',
            'response_time': db_metrics['avg_response_time'],
            'failover_count': db_metrics['failover_count']
        }

    def _calculate_error_rate(self) -> Dict:
        """Calculate system error rates"""
        try:
            hour_ago = datetime.utcnow() - timedelta(hours=1)
            total_errors = ErrorLog.query.filter(
                ErrorLog.timestamp > hour_ago
            ).count()

            error_types = db.session.query(
                ErrorLog.error_type,
                func.count(ErrorLog.id)
            ).filter(
                ErrorLog.timestamp > hour_ago
            ).group_by(ErrorLog.error_type).all()

            return {
                'hourly_rate': total_errors,
                'error_distribution': dict(error_types)
            }
        except Exception as e:
            logger.error(f"Error rate calculation failed: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def _check_performance_metrics(self) -> Dict:
        """Check system performance metrics"""
        try:
            hour_ago = datetime.utcnow() - timedelta(hours=1)
            metrics = {
                'transaction_count': Transaction.query.filter(
                    Transaction.created_at > hour_ago
                ).count(),
                'active_accounts': Account.query.filter_by(is_active=True).count()
            }
            return metrics
        except Exception as e:
            logger.error(f"Performance check failed: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def _check_resource_usage(self) -> Dict:
        """Check system resource usage"""
        try:
            import psutil
            return {
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': psutil.disk_usage('/').percent
            }
        except ImportError:
            return {'status': 'unavailable', 'message': 'psutil not installed'}

    def predict_maintenance_needs(self) -> List[Dict]:
        """Predict maintenance needs based on system metrics"""
        if not self.health_metrics:
            self.check_system_health()

        predictions = []
        metrics = self.health_metrics

        # Database health predictions
        if metrics['database']['status'] == 'degraded':
            predictions.append({
                'component': 'database',
                'priority': 'high',
                'prediction': 'Database performance degradation detected',
                'recommendation': 'Schedule maintenance window for database optimization'
            })

        # Error rate predictions
        error_rate = metrics.get('error_rate', {}).get('hourly_rate', 0)
        if error_rate > 100:
            predictions.append({
                'component': 'application',
                'priority': 'high',
                'prediction': f'High error rate detected: {error_rate} errors/hour',
                'recommendation': 'Investigate error patterns and implement fixes'
            })

        # Resource usage predictions
        resource_metrics = metrics.get('resource_usage', {})
        if resource_metrics.get('memory_percent', 0) > 80:
            predictions.append({
                'component': 'system',
                'priority': 'medium',
                'prediction': 'High memory usage detected',
                'recommendation': 'Consider memory optimization or scaling'
            })

        return predictions

    def get_health_dashboard_data(self) -> Dict:
        """Get data for health dashboard"""
        self.check_system_health()
        return {
            'metrics': self.health_metrics,
            'predictions': self.predict_maintenance_needs(),
            'last_update': datetime.utcnow().isoformat()
        }
class MaintenanceMonitor:
    def __init__(self):
        self.db_health = DatabaseHealth.get_instance()
        self.logger = logging.getLogger(__name__)
        
    def check_module_health(self, user_id=None):
        health_status = {
            'database': self._check_database_health(),
            'ai_service': self._check_ai_service_health(),
            'error_monitoring': self._check_error_logs(),
            'timestamp': datetime.now().isoformat()
        }
        
        if any(not status['healthy'] for status in health_status.values() if isinstance(status, dict)):
            self.logger.warning(f"System health check failed: {health_status}")
            
        return health_status
        
    def _check_database_health(self):
        metrics = self.db_health.get_health_metrics()
        return {
            'healthy': metrics['consecutive_failures'] == 0,
            'metrics': metrics
        }

    def _check_ai_service_health(self):
        try:
            ai_service = FinancialInsightsGenerator()
            health = ai_service.get_service_health()
            return {
                'healthy': health['status'] == 'healthy',
                'metrics': health
            }
        except Exception as e:
            self.logger.error(f"AI service health check failed: {str(e)}")
            return {
                'healthy': False,
                'error': str(e)
            }

    def _check_error_logs(self):
        try:
            recent_errors = ErrorLog.query.filter(
                ErrorLog.timestamp >= datetime.now() - timedelta(hours=1)
            ).count()
            
            return {
                'healthy': recent_errors < 5,
                'recent_error_count': recent_errors
            }
        except Exception as e:
            self.logger.error(f"Error log check failed: {str(e)}")
            return {
                'healthy': False,
                'error': str(e)
            }
