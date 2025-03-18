"""
System Auditor Module

Provides comprehensive system health monitoring capabilities for automated audits.
"""

import os
import logging
import psutil
import platform
import time
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

import sqlalchemy
from sqlalchemy.exc import SQLAlchemyError
import urllib.request
import socket

from models import db

logger = logging.getLogger(__name__)

class SystemAuditorResult:
    """Class to store system audit results"""
    def __init__(self):
        self.checks = {}
        self.issues = []
        self.start_time = datetime.utcnow()
        self.end_time = None
        self.duration = 0.0
    
    def add_check(self, component: str, metric: str, value: Any, status: str = 'ok', threshold: Any = None):
        """Add check result"""
        self.checks[f"{component}_{metric}"] = {
            'component': component,
            'metric': metric,
            'value': value,
            'status': status,
            'threshold': threshold,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def add_issue(self, title: str, description: str, component: str, severity: str, 
                 metric: Optional[str] = None, value: Optional[Any] = None, threshold: Optional[Any] = None,
                 recommendation: Optional[str] = None):
        """Add a detected issue"""
        if recommendation is None:
            recommendation = "Review and address the issue."
            
        # Normalize severity
        if severity not in ['critical', 'high', 'medium', 'low']:
            severity = 'medium'
            
        self.issues.append({
            'title': title,
            'description': description,
            'component': component,
            'metric': metric,
            'value': value,
            'threshold': threshold,
            'severity': severity,
            'recommendation': recommendation,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    def get_results(self) -> Dict[str, Any]:
        """Get comprehensive audit results"""
        # Calculate audit duration
        if self.end_time is None:
            self.end_time = datetime.utcnow()
        
        self.duration = (self.end_time - self.start_time).total_seconds()
        
        # Extract key metrics for quick reference
        cpu_usage = None
        memory_usage = None
        disk_usage = None
        
        if 'system_cpu_percent' in self.checks:
            cpu_usage = self.checks['system_cpu_percent']['value']
        
        if 'system_memory_percent' in self.checks:
            memory_usage = self.checks['system_memory_percent']['value']
        
        if 'system_disk_percent' in self.checks:
            disk_usage = self.checks['system_disk_percent']['value']
            
        # Database connection status
        db_connection = 'unknown'
        if 'database_connection_status' in self.checks:
            db_connection = self.checks['database_connection_status']['status']
        
        # Response time for main endpoints
        response_time = None
        if 'web_response_time' in self.checks:
            response_time = self.checks['web_response_time']['value']
        
        return {
            'duration': self.duration,
            'timestamp': datetime.utcnow().isoformat(),
            'cpu_usage': cpu_usage,
            'memory_usage': memory_usage,
            'disk_usage': disk_usage,
            'database_connection': db_connection,
            'response_time': response_time,
            'checks': self.checks,
            'issues': self.issues,
            'issue_count': len(self.issues)
        }


class SystemAuditor:
    """Audits system health and performance"""
    
    def __init__(self):
        self.result = SystemAuditorResult()
        self.critical_cpu_threshold = 90.0  # %
        self.warning_cpu_threshold = 75.0   # %
        self.critical_memory_threshold = 90.0  # %
        self.warning_memory_threshold = 80.0   # %
        self.critical_disk_threshold = 90.0   # %
        self.warning_disk_threshold = 80.0    # %
        self.slow_response_threshold = 1.0    # second
        
    def audit_system(self) -> SystemAuditorResult:
        """
        Perform a comprehensive system audit
        
        Returns:
            SystemAuditorResult: Object containing all audit results
        """
        logger.info("Starting comprehensive system audit")
        
        try:
            # Check system resources
            self._check_system_resources()
            
            # Check database health
            self._check_database_health()
            
            # Check application health
            self._check_application_health()
            
            # Check process information
            self._check_process_info()
            
            # Final reporting
            self.result.end_time = datetime.utcnow()
            logger.info(f"System audit completed in {self.result.duration:.2f} seconds with {len(self.result.issues)} issues found")
            
        except Exception as e:
            logger.exception(f"Error during system audit: {str(e)}")
            self.result.add_issue(
                title="System Audit Error",
                description=f"Failed to complete system audit: {str(e)}",
                component="auditor",
                severity="high",
                recommendation="Check system auditor logs and fix the underlying issue."
            )
        
        return self.result
    
    def _check_system_resources(self):
        """Check system CPU, memory, and disk usage"""
        # CPU usage
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            self.result.add_check('system', 'cpu_percent', cpu_percent)
            
            if cpu_percent >= self.critical_cpu_threshold:
                self.result.add_issue(
                    title="Critical CPU Usage",
                    description=f"CPU usage is at {cpu_percent}%, which exceeds critical threshold of {self.critical_cpu_threshold}%",
                    component="system",
                    metric="cpu_percent",
                    value=cpu_percent,
                    threshold=self.critical_cpu_threshold,
                    severity="critical",
                    recommendation="Identify and terminate CPU-intensive processes or scale up the system."
                )
            elif cpu_percent >= self.warning_cpu_threshold:
                self.result.add_issue(
                    title="High CPU Usage",
                    description=f"CPU usage is at {cpu_percent}%, which exceeds warning threshold of {self.warning_cpu_threshold}%",
                    component="system",
                    metric="cpu_percent",
                    value=cpu_percent,
                    threshold=self.warning_cpu_threshold,
                    severity="medium",
                    recommendation="Monitor CPU usage and consider optimizing code or scaling up if trend continues."
                )
                
            # CPU count and frequency
            cpu_info = {
                'count': psutil.cpu_count(logical=True),
                'physical_count': psutil.cpu_count(logical=False)
            }
            self.result.add_check('system', 'cpu_info', cpu_info)
            
        except Exception as e:
            logger.error(f"Error checking CPU: {str(e)}")
            self.result.add_check('system', 'cpu_percent', None, status='error')
        
        # Memory usage
        try:
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_info = {
                'total': memory.total,
                'available': memory.available,
                'used': memory.used,
                'percent': memory_percent
            }
            self.result.add_check('system', 'memory_info', memory_info)
            self.result.add_check('system', 'memory_percent', memory_percent)
            
            if memory_percent >= self.critical_memory_threshold:
                self.result.add_issue(
                    title="Critical Memory Usage",
                    description=f"Memory usage is at {memory_percent}%, which exceeds critical threshold of {self.critical_memory_threshold}%",
                    component="system",
                    metric="memory_percent",
                    value=memory_percent,
                    threshold=self.critical_memory_threshold,
                    severity="critical",
                    recommendation="Identify memory leaks or high-consumption processes and address them immediately."
                )
            elif memory_percent >= self.warning_memory_threshold:
                self.result.add_issue(
                    title="High Memory Usage",
                    description=f"Memory usage is at {memory_percent}%, which exceeds warning threshold of {self.warning_memory_threshold}%",
                    component="system",
                    metric="memory_percent",
                    value=memory_percent,
                    threshold=self.warning_memory_threshold,
                    severity="medium",
                    recommendation="Monitor memory usage and optimize memory-intensive operations."
                )
                
        except Exception as e:
            logger.error(f"Error checking memory: {str(e)}")
            self.result.add_check('system', 'memory_percent', None, status='error')
        
        # Disk usage
        try:
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            disk_info = {
                'total': disk.total,
                'used': disk.used,
                'free': disk.free,
                'percent': disk_percent
            }
            self.result.add_check('system', 'disk_info', disk_info)
            self.result.add_check('system', 'disk_percent', disk_percent)
            
            if disk_percent >= self.critical_disk_threshold:
                self.result.add_issue(
                    title="Critical Disk Usage",
                    description=f"Disk usage is at {disk_percent}%, which exceeds critical threshold of {self.critical_disk_threshold}%",
                    component="system",
                    metric="disk_percent",
                    value=disk_percent,
                    threshold=self.critical_disk_threshold,
                    severity="critical",
                    recommendation="Clean up unnecessary files or add more storage space immediately."
                )
            elif disk_percent >= self.warning_disk_threshold:
                self.result.add_issue(
                    title="High Disk Usage",
                    description=f"Disk usage is at {disk_percent}%, which exceeds warning threshold of {self.warning_disk_threshold}%",
                    component="system",
                    metric="disk_percent",
                    value=disk_percent,
                    threshold=self.warning_disk_threshold,
                    severity="medium",
                    recommendation="Review disk usage and plan for cleanup or expansion."
                )
                
        except Exception as e:
            logger.error(f"Error checking disk: {str(e)}")
            self.result.add_check('system', 'disk_percent', None, status='error')
    
    def _check_database_health(self):
        """Check database connection and performance"""
        try:
            # Basic connection check
            start_time = time.time()
            connection_test = None
            try:
                # Simple query to test connection
                connection_test = db.session.execute("SELECT 1").scalar()
                connection_status = 'ok' if connection_test == 1 else 'error'
            except SQLAlchemyError as e:
                connection_status = 'error'
                connection_error = str(e)
                self.result.add_issue(
                    title="Database Connection Error",
                    description=f"Failed to connect to database: {connection_error}",
                    component="database",
                    severity="critical",
                    recommendation="Check database settings and ensure the database service is running."
                )
            
            query_time = time.time() - start_time
            
            self.result.add_check('database', 'connection_status', connection_test, status=connection_status)
            self.result.add_check('database', 'query_time', query_time)
            
            # If connection was successful, check more details
            if connection_status == 'ok':
                # Check table sizes (simplified for demo)
                table_counts = {}
                for table_name in ['users', 'accounts', 'transactions', 'audit_logs']:
                    try:
                        count = db.session.execute(f"SELECT COUNT(*) FROM {table_name}").scalar()
                        table_counts[table_name] = count
                    except SQLAlchemyError:
                        table_counts[table_name] = "error"
                
                self.result.add_check('database', 'table_counts', table_counts)
                
                # Check database engine info
                if hasattr(db, 'engine'):
                    db_info = {
                        'dialect': db.engine.dialect.name if hasattr(db.engine, 'dialect') else 'unknown',
                        'driver': db.engine.driver if hasattr(db.engine, 'driver') else 'unknown'
                    }
                    self.result.add_check('database', 'engine_info', db_info)
        
        except Exception as e:
            logger.error(f"Error checking database health: {str(e)}")
            self.result.add_check('database', 'connection_status', None, status='error')
            self.result.add_issue(
                title="Database Check Error",
                description=f"Failed to check database health: {str(e)}",
                component="database",
                severity="high",
                recommendation="Investigate the error and fix database monitoring."
            )
    
    def _check_application_health(self):
        """Check application health and response times"""
        try:
            # Local endpoint health check
            local_endpoints = [('localhost', 5000, '/')]
            
            for host, port, path in local_endpoints:
                try:
                    start_time = time.time()
                    conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    conn.settimeout(2.0)
                    conn.connect((host, port))
                    conn.close()
                    
                    response_time = time.time() - start_time
                    endpoint_status = 'ok'
                    
                    # Check if response time is slow
                    if response_time > self.slow_response_threshold:
                        self.result.add_issue(
                            title="Slow Application Response",
                            description=f"Endpoint {host}:{port}{path} response time ({response_time:.2f}s) exceeds threshold ({self.slow_response_threshold}s)",
                            component="web",
                            metric="response_time",
                            value=response_time,
                            threshold=self.slow_response_threshold,
                            severity="medium",
                            recommendation="Investigate application performance and optimize slow endpoints."
                        )
                except (socket.timeout, socket.error, ConnectionRefusedError) as e:
                    response_time = None
                    endpoint_status = 'error'
                    self.result.add_issue(
                        title="Application Endpoint Unavailable",
                        description=f"Failed to connect to endpoint {host}:{port}{path}: {str(e)}",
                        component="web",
                        severity="critical",
                        recommendation="Check if the application server is running and listening on the expected port."
                    )
                
                self.result.add_check('web', 'response_time', response_time, status=endpoint_status)
                
        except Exception as e:
            logger.error(f"Error checking application health: {str(e)}")
            self.result.add_check('web', 'response_time', None, status='error')
            self.result.add_issue(
                title="Application Health Check Error",
                description=f"Failed to check application health: {str(e)}",
                component="web",
                severity="medium",
                recommendation="Investigate the error and fix application monitoring."
            )
    
    def _check_process_info(self):
        """Check process information and resource usage"""
        try:
            # Get own process info
            process = psutil.Process(os.getpid())
            
            # Process memory usage
            process_memory = process.memory_info()
            memory_usage = {
                'rss': process_memory.rss,  # Resident Set Size
                'vms': process_memory.vms,  # Virtual Memory Size
                'percent': process.memory_percent()
            }
            self.result.add_check('process', 'memory_usage', memory_usage)
            
            # Process CPU usage
            process_cpu = process.cpu_percent(interval=0.5)
            self.result.add_check('process', 'cpu_percent', process_cpu)
            
            # Process age and open files
            process_create_time = datetime.fromtimestamp(process.create_time())
            process_age = (datetime.now() - process_create_time).total_seconds()
            process_info = {
                'pid': process.pid,
                'age': process_age,
                'threads': process.num_threads(),
                'create_time': process_create_time.isoformat()
            }
            self.result.add_check('process', 'info', process_info)
            
            # Check if process is using too much memory
            if memory_usage['percent'] > 25.0:  # Arbitrary threshold
                self.result.add_issue(
                    title="High Process Memory Usage",
                    description=f"Application process is using {memory_usage['percent']:.1f}% of system memory",
                    component="process",
                    metric="memory_percent",
                    value=memory_usage['percent'],
                    threshold=25.0,
                    severity="medium",
                    recommendation="Check for memory leaks or optimize memory-intensive operations."
                )
            
            # Check if process has been running for too long (potential memory leaks)
            if process_age > 86400:  # 24 hours
                self.result.add_issue(
                    title="Long-Running Process",
                    description=f"Application process has been running for {process_age/3600:.1f} hours",
                    component="process",
                    metric="age",
                    value=process_age,
                    threshold=86400,
                    severity="low",
                    recommendation="Consider periodic process restarts to mitigate potential memory leaks."
                )
                
        except Exception as e:
            logger.error(f"Error checking process info: {str(e)}")
            self.result.add_check('process', 'info', None, status='error')