"""
System auditor for automated performance monitoring and application health checks
"""
import os
import sys
import time
import logging
import platform
import threading
import traceback
from datetime import datetime
import subprocess
import psutil
from typing import Dict, List, Any, Tuple
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SystemAuditorResult:
    """Class to store system audit results"""
    def __init__(self):
        self.findings = []
        self.stats = {
            'cpu_usage': None,
            'memory_usage': None,
            'disk_usage': None,
            'db_connection_count': None,
            'db_slow_queries': 0,
            'api_response_time': None,
            'error_rate': None
        }
    
    def add_finding(self, category: str, severity: str, title: str, description: str, recommendation: str = None):
        """Add a detected issue to the results"""
        self.findings.append({
            'category': category,
            'severity': severity.lower(),  # normalize severity
            'title': title,
            'description': description,
            'recommendation': recommendation,
            'timestamp': datetime.utcnow()
        })
    
    def set_stat(self, key: str, value: Any):
        """Set a statistic value"""
        if key in self.stats:
            self.stats[key] = value
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the audit results"""
        return {
            'stats': self.stats,
            'findings': self.findings,
            'timestamp': datetime.utcnow().isoformat()
        }

class SystemAuditor:
    """Performs system audits to detect performance issues and application health problems"""
    
    def __init__(self, app=None, db=None):
        self.app = app
        self.db = db
        self.results = SystemAuditorResult()
    
    def run_comprehensive_audit(self) -> Dict[str, Any]:
        """Run all audit checks and return results"""
        logger.info("Starting comprehensive system audit")
        
        # Reset results
        self.results = SystemAuditorResult()
        
        try:
            # System resource checks
            self._check_system_resources()
            
            # Database health checks
            if self.db is not None:
                self._check_database_health()
            
            # Application error rate
            self._check_error_rates()
            
            # Code quality analysis
            self._check_code_quality()
            
            # Filesystem checks
            self._check_filesystem_health()
            
            # Log analysis 
            self._analyze_logs()
            
            # Config checks
            self._check_configurations()
            
            logger.info("Comprehensive system audit complete")
        except Exception as e:
            logger.error(f"Error during system audit: {str(e)}")
            self.results.add_finding(
                category="audit_error",
                severity="high",
                title="System audit encountered an error",
                description=f"Error during system audit: {str(e)}",
                recommendation="Check the logs for more details and address the underlying issue."
            )
        
        return self.results.get_summary()
    
    def _check_system_resources(self):
        """Check system resource usage"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.results.set_stat('cpu_usage', cpu_percent)
            
            if cpu_percent > 80:
                self.results.add_finding(
                    category="resource",
                    severity="high",
                    title="High CPU usage detected",
                    description=f"CPU usage is at {cpu_percent}%, which may cause application slowdowns",
                    recommendation="Consider optimizing CPU-intensive operations or scaling up resources."
                )
            elif cpu_percent > 60:
                self.results.add_finding(
                    category="resource",
                    severity="medium",
                    title="Elevated CPU usage detected",
                    description=f"CPU usage is at {cpu_percent}%, which is higher than optimal",
                    recommendation="Monitor application performance and optimize CPU usage if needed."
                )
            
            # Memory usage
            memory = psutil.virtual_memory()
            mem_percent = memory.percent
            self.results.set_stat('memory_usage', mem_percent)
            
            if mem_percent > 85:
                self.results.add_finding(
                    category="resource",
                    severity="high",
                    title="High memory usage detected",
                    description=f"Memory usage is at {mem_percent}%, which may lead to swapping or OOM errors",
                    recommendation="Check for memory leaks, excessive caching, or large object allocations."
                )
            elif mem_percent > 70:
                self.results.add_finding(
                    category="resource",
                    severity="medium",
                    title="Elevated memory usage detected",
                    description=f"Memory usage is at {mem_percent}%, which is higher than optimal",
                    recommendation="Monitor memory usage trends and optimize if it continues to increase."
                )
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            self.results.set_stat('disk_usage', disk_percent)
            
            if disk_percent > 90:
                self.results.add_finding(
                    category="resource",
                    severity="critical",
                    title="Critical disk space shortage",
                    description=f"Disk usage is at {disk_percent}%, which may cause application failures",
                    recommendation="Free up disk space immediately or expand disk capacity."
                )
            elif disk_percent > 75:
                self.results.add_finding(
                    category="resource",
                    severity="high",
                    title="Low disk space detected",
                    description=f"Disk usage is at {disk_percent}%, which is approaching critical levels",
                    recommendation="Clean up temporary files or logs, and plan for disk space expansion."
                )
            
        except Exception as e:
            logger.error(f"Error checking system resources: {str(e)}")
            self.results.add_finding(
                category="audit_error",
                severity="medium",
                title="Failed to check system resources",
                description=f"Error: {str(e)}",
                recommendation="Ensure the application has permissions to monitor system resources."
            )
    
    def _check_database_health(self):
        """Check database performance and health"""
        try:
            if self.db is None:
                return
            
            with self.app.app_context():
                # Check connection count
                try:
                    result = self.db.session.execute(text("SELECT count(*) FROM pg_stat_activity"))
                    conn_count = result.scalar()
                    self.results.set_stat('db_connection_count', conn_count)
                    
                    if conn_count > 20:  # Arbitrary threshold
                        self.results.add_finding(
                            category="database",
                            severity="medium",
                            title="High number of database connections",
                            description=f"There are {conn_count} active database connections",
                            recommendation="Check for connection leaks and ensure proper connection pooling."
                        )
                except Exception as e:
                    # This might fail with SQLite or if DB permissions are insufficient
                    logger.info(f"Could not check connection count: {str(e)}")
                
                # Check for long-running queries (PostgreSQL only)
                try:
                    result = self.db.session.execute(text(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE state = 'active' AND (now() - query_start) > interval '5 seconds'"
                    ))
                    slow_queries = result.scalar()
                    self.results.set_stat('db_slow_queries', slow_queries)
                    
                    if slow_queries > 0:
                        self.results.add_finding(
                            category="database",
                            severity="high",
                            title="Slow database queries detected",
                            description=f"There are {slow_queries} queries running for more than 5 seconds",
                            recommendation="Optimize slow queries by adding indexes or restructuring the queries."
                        )
                except Exception as e:
                    # This will fail with SQLite
                    logger.info(f"Could not check for slow queries: {str(e)}")
                
                # Check for recent errors
                try:
                    from models import ErrorLog
                    recent_errors = ErrorLog.query.filter(
                        ErrorLog.timestamp >= datetime.utcnow().replace(hour=0, minute=0, second=0)
                    ).count()
                    
                    if recent_errors > 10:  # Arbitrary threshold
                        self.results.add_finding(
                            category="application",
                            severity="high",
                            title="High error rate detected",
                            description=f"There have been {recent_errors} errors logged today",
                            recommendation="Investigate the error logs to identify and fix common errors."
                        )
                except Exception as e:
                    logger.error(f"Could not check error logs: {str(e)}")
        
        except Exception as e:
            logger.error(f"Error checking database health: {str(e)}")
            self.results.add_finding(
                category="database",
                severity="medium",
                title="Failed to check database health",
                description=f"Error: {str(e)}",
                recommendation="Check database connectivity and permissions."
            )
    
    def _check_error_rates(self):
        """Check application error rates from logs"""
        try:
            error_count = 0
            request_count = 0
            
            # Analyze Flask log files
            log_files = ['app.log', 'error.log']
            for log_file in log_files:
                if os.path.exists(log_file):
                    with open(log_file, 'r') as f:
                        for line in f:
                            if 'ERROR' in line:
                                error_count += 1
                            if 'GET /' in line or 'POST /' in line:
                                request_count += 1
            
            # Calculate error rate if we have requests
            if request_count > 0:
                error_rate = (error_count / request_count) * 100
                self.results.set_stat('error_rate', error_rate)
                
                if error_rate > 5:  # 5% arbitrary threshold
                    self.results.add_finding(
                        category="application",
                        severity="critical",
                        title="High application error rate",
                        description=f"Error rate is {error_rate:.2f}% ({error_count} errors in {request_count} requests)",
                        recommendation="Investigate error logs and fix the most common errors."
                    )
                elif error_rate > 1:  # 1% arbitrary threshold
                    self.results.add_finding(
                        category="application",
                        severity="high",
                        title="Elevated application error rate",
                        description=f"Error rate is {error_rate:.2f}% ({error_count} errors in {request_count} requests)",
                        recommendation="Monitor error logs and address recurring issues."
                    )
            
        except Exception as e:
            logger.error(f"Error checking error rates: {str(e)}")
            self.results.add_finding(
                category="audit_error",
                severity="low",
                title="Failed to check error rates",
                description=f"Error: {str(e)}",
                recommendation="Ensure the application has read access to log files."
            )
    
    def _check_code_quality(self):
        """Run code quality checks"""
        try:
            from utils.code_analyzer import analyze_code
            
            code_analysis = analyze_code('.')
            
            # Add findings based on code analysis results
            issue_count = code_analysis['stats']['issues_found']
            critical_issues = code_analysis['stats']['critical_issues']
            high_issues = code_analysis['stats']['high_issues']
            
            if critical_issues > 0:
                self.results.add_finding(
                    category="code_quality",
                    severity="critical",
                    title=f"Critical code issues detected ({critical_issues})",
                    description=f"Found {critical_issues} critical issues in the codebase that need immediate attention",
                    recommendation="Address critical issues as soon as possible to prevent security vulnerabilities or system failures."
                )
            
            if high_issues > 0:
                self.results.add_finding(
                    category="code_quality",
                    severity="high",
                    title=f"High-severity code issues detected ({high_issues})",
                    description=f"Found {high_issues} high-severity issues in the codebase",
                    recommendation="Review and fix high severity issues to improve application stability and security."
                )
            
            if issue_count > 10 and (critical_issues + high_issues) < issue_count:
                self.results.add_finding(
                    category="code_quality",
                    severity="medium",
                    title=f"Multiple code quality issues ({issue_count})",
                    description=f"Found {issue_count} total code quality issues",
                    recommendation="Implement a code review process and fix issues systematically."
                )
            
            # Add specific top issues
            for issue in code_analysis['top_issues']:
                self.results.add_finding(
                    category="code_quality",
                    severity=issue['severity'],
                    title=f"{issue['issue_type']} in {os.path.basename(issue['file_path'])}",
                    description=f"Line {issue['line_number']}: {issue['description']}",
                    recommendation=issue['recommendation']
                )
            
        except Exception as e:
            logger.error(f"Error during code quality check: {str(e)}")
            self.results.add_finding(
                category="audit_error",
                severity="low",
                title="Failed to check code quality",
                description=f"Error: {str(e)}",
                recommendation="Check if code analysis dependencies are properly installed."
            )
    
    def _check_filesystem_health(self):
        """Check for filesystem issues like many temp files or excessive log sizes"""
        try:
            # Check log file sizes
            log_files = [f for f in os.listdir('.') if f.endswith('.log')]
            for log_file in log_files:
                file_size_mb = os.path.getsize(log_file) / (1024 * 1024)  # Convert to MB
                
                if file_size_mb > 100:  # 100MB arbitrary threshold
                    self.results.add_finding(
                        category="filesystem",
                        severity="medium",
                        title="Excessively large log file",
                        description=f"Log file {log_file} is {file_size_mb:.1f} MB",
                        recommendation="Implement log rotation to prevent disk space issues."
                    )
            
            # Check for temp files
            temp_files = [f for f in os.listdir('.') if f.startswith('tmp') or f.endswith('.tmp')]
            if len(temp_files) > 20:  # Arbitrary threshold
                self.results.add_finding(
                    category="filesystem",
                    severity="low",
                    title="Excessive temporary files",
                    description=f"Found {len(temp_files)} temporary files",
                    recommendation="Implement cleanup procedures for temporary files."
                )
            
            # Check for permissions (Unix systems only)
            if os.name == 'posix':
                sensitive_folders = ['templates', 'static', 'instance']
                for folder in sensitive_folders:
                    if os.path.exists(folder):
                        permissions = oct(os.stat(folder).st_mode)[-3:]
                        if permissions == '777':
                            self.results.add_finding(
                                category="security",
                                severity="high",
                                title="Insecure folder permissions",
                                description=f"Folder '{folder}' has world-writable permissions (777)",
                                recommendation="Change folder permissions to more restrictive settings."
                            )
            
        except Exception as e:
            logger.error(f"Error checking filesystem health: {str(e)}")
            self.results.add_finding(
                category="audit_error",
                severity="low",
                title="Failed to check filesystem health",
                description=f"Error: {str(e)}",
                recommendation="Ensure the application has filesystem access permissions."
            )
    
    def _analyze_logs(self):
        """Analyze log files for patterns and issues"""
        try:
            # Error patterns to look for
            error_patterns = {
                "connection timeout": "database_timeout",
                "deadlock": "database_deadlock",
                "memory error": "memory_issue",
                "api rate limit": "rate_limit",
                "too many connections": "connection_limit",
                "permission denied": "permission_issue"
            }
            
            error_counts = {key: 0 for key in error_patterns.values()}
            
            # Analyze error logs
            log_files = ['app.log', 'error.log', 'database.log']
            for log_file in log_files:
                if os.path.exists(log_file):
                    with open(log_file, 'r') as f:
                        for line in f:
                            for pattern, category in error_patterns.items():
                                if pattern.lower() in line.lower():
                                    error_counts[category] += 1
            
            # Report findings based on error patterns
            for category, count in error_counts.items():
                if count > 5:  # Arbitrary threshold
                    severity = "high" if count > 10 else "medium"
                    
                    # Create a human-readable title based on the category
                    title_map = {
                        "database_timeout": "Database connection timeouts",
                        "database_deadlock": "Database deadlocks detected",
                        "memory_issue": "Memory-related errors",
                        "rate_limit": "API rate limit issues",
                        "connection_limit": "Too many connections errors",
                        "permission_issue": "Permission denied errors"
                    }
                    
                    title = title_map.get(category, f"{category.replace('_', ' ').title()}")
                    
                    # Create appropriate recommendations
                    recommendation_map = {
                        "database_timeout": "Check database connection settings and network stability.",
                        "database_deadlock": "Review transaction isolation levels and query patterns to prevent deadlocks.",
                        "memory_issue": "Check for memory leaks and increase available memory if needed.",
                        "rate_limit": "Implement rate limiting and caching to prevent API overuse.",
                        "connection_limit": "Optimize connection pooling and increase connection limits if possible.",
                        "permission_issue": "Check file and resource permissions for the application user."
                    }
                    
                    recommendation = recommendation_map.get(category, "Investigate logs for more details on this issue.")
                    
                    self.results.add_finding(
                        category="log_analysis",
                        severity=severity,
                        title=title,
                        description=f"Found {count} occurrences of {category.replace('_', ' ')} in logs",
                        recommendation=recommendation
                    )
            
        except Exception as e:
            logger.error(f"Error analyzing logs: {str(e)}")
            self.results.add_finding(
                category="audit_error",
                severity="low",
                title="Failed to analyze logs",
                description=f"Error: {str(e)}",
                recommendation="Check file permissions for log files."
            )
    
    def _check_configurations(self):
        """Check application configuration for security and performance issues"""
        try:
            if not self.app:
                return
                
            # Check for missing security configurations
            if not self.app.config.get('SECRET_KEY'):
                self.results.add_finding(
                    category="security",
                    severity="critical",
                    title="Missing SECRET_KEY",
                    description="Application is missing a SECRET_KEY configuration",
                    recommendation="Set a strong, unique SECRET_KEY for cryptographic operations."
                )
            
            # Check for insecure configurations
            if self.app.config.get('DEBUG') is True:
                self.results.add_finding(
                    category="security",
                    severity="high",
                    title="Debug mode enabled",
                    description="Application is running in DEBUG mode, which is not secure for production",
                    recommendation="Disable DEBUG mode in production environments."
                )
            
            # Check database connection pool settings
            if self.app.config.get('SQLALCHEMY_ENGINE_OPTIONS'):
                pool_options = self.app.config.get('SQLALCHEMY_ENGINE_OPTIONS')
                if pool_options.get('pool_size', 5) < 3:
                    self.results.add_finding(
                        category="performance",
                        severity="low",
                        title="Small database connection pool",
                        description="Database connection pool size is set very low",
                        recommendation="Consider increasing pool_size for better performance under load."
                    )
            
            # Check session security
            if not self.app.config.get('PERMANENT_SESSION_LIFETIME'):
                self.results.add_finding(
                    category="security",
                    severity="medium",
                    title="No session lifetime configured",
                    description="No explicit session lifetime is configured",
                    recommendation="Set PERMANENT_SESSION_LIFETIME to limit session duration."
                )
            
        except Exception as e:
            logger.error(f"Error checking configurations: {str(e)}")
            self.results.add_finding(
                category="audit_error",
                severity="low",
                title="Failed to check configurations",
                description=f"Error: {str(e)}",
                recommendation="Ensure the application configuration is accessible."
            )

def run_system_audit(app=None, db=None) -> Dict[str, Any]:
    """Run a comprehensive system audit"""
    auditor = SystemAuditor(app, db)
    return auditor.run_comprehensive_audit()