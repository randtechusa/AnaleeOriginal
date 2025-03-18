"""
Scheduled Audit Module

Provides automated audit functionality with code analysis and system health monitoring.
This module runs daily comprehensive audits at 8:00 PM ET.
"""

import logging
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError
import traceback
import psutil
from datetime import datetime, timedelta
import pytz
import os
import json

from models import db, SystemAudit, AuditFinding
from utils.code_analyzer import CodeAnalyzer
from utils.system_auditor import SystemAuditor
from utils.audit_service import AuditService

logger = logging.getLogger(__name__)
audit_service = AuditService()

def setup_scheduled_audits(app):
    """
    Setup scheduled audit jobs
    
    Args:
        app: Flask application instance
    """
    if not hasattr(app, 'scheduler'):
        logger.warning("No scheduler available - scheduled audits not configured")
        return
    
    try:
        # Create a job for daily audit at 8:00 PM Eastern Time
        eastern = pytz.timezone('US/Eastern')
        from utils.scheduler import add_scheduled_job
        
        # Use our enhanced scheduler function
        add_scheduled_job(
            id='daily_system_audit',
            func=run_daily_audit,
            trigger='cron',
            hour=20,  # 8:00 PM
            minute=0,
            timezone=eastern
        )
        
        logger.info("Scheduled daily audit configured for 8:00 PM ET")
        
        # Log setup
        audit_service.log_activity(
            user_id=None,
            action='configure',
            resource_type='scheduled_audit',
            resource_id=None,
            description="Configured daily system audit for 8:00 PM ET",
            status='success'
        )
    except Exception as e:
        logger.error(f"Error setting up scheduled audit: {str(e)}")
        
        # Log error
        audit_service.log_activity(
            user_id=None,
            action='configure',
            resource_type='scheduled_audit',
            resource_id=None,
            description=f"Failed to configure scheduled audit: {str(e)}",
            status='failure'
        )

def run_daily_audit():
    """
    Run the daily comprehensive audit
    
    Returns:
        tuple: (success_flag, message, audit_id)
    """
    # Define audit_id at the beginning to avoid 'possibly unbound' errors
    audit_id = None
    
    try:
        # Create audit record
        audit = SystemAudit(
            audit_type='daily_comprehensive',
            user_id=None,  # System-generated
            status='running',
            summary='Daily automated audit in progress',
            duration=0.0
        )
        
        db.session.add(audit)
        db.session.commit()
        audit_id = audit.id
        
        # Log start
        audit_service.log_activity(
            user_id=None,
            action='start',
            resource_type='scheduled_audit',
            resource_id=audit_id,
            description="Started daily automated system audit",
            status='success'
        )
        
        # Perform the audit
        start_time = datetime.utcnow()
        
        # Call different audit modules
        findings = []
        results = {}
        
        # 1. Code quality audit
        code_results, code_findings = perform_code_quality_audit(audit_id)
        findings.extend(code_findings)
        results['code_quality'] = code_results
        
        # 2. System health audit  
        system_results, system_findings = perform_system_health_audit(audit_id)
        findings.extend(system_findings)
        results['system_health'] = system_results
        
        # 3. Database audit
        db_results, db_findings = perform_database_audit(audit_id)
        findings.extend(db_findings)
        results['database'] = db_results
        
        # Calculate duration
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        # Determine status
        if any(f.severity == 'critical' for f in findings):
            status = 'failed'
        elif any(f.severity in ['high', 'medium'] for f in findings):
            status = 'warning'
        else:
            status = 'passed'
            
        # Generate summary
        critical_count = sum(1 for f in findings if f.severity == 'critical')
        high_count = sum(1 for f in findings if f.severity == 'high')
        medium_count = sum(1 for f in findings if f.severity == 'medium')
        low_count = sum(1 for f in findings if f.severity == 'low')
        
        summary = f"Daily audit completed with {len(findings)} findings. "
        
        if critical_count:
            summary += f"{critical_count} critical, "
        if high_count:
            summary += f"{high_count} high, "
        if medium_count:
            summary += f"{medium_count} medium, "
        if low_count:
            summary += f"{low_count} low "
            
        summary += "severity issues found."
        
        # Update audit record
        audit.status = status
        audit.summary = summary
        audit.duration = duration
        audit.details = json.dumps(results)
        audit.completed_at = end_time
        
        db.session.commit()
        
        # Log completion
        audit_service.log_activity(
            user_id=None,
            action='complete',
            resource_type='scheduled_audit',
            resource_id=audit_id,
            description=f"Completed daily audit with status: {status}",
            status='success'
        )
        
        return True, f"Audit completed: {summary}", audit_id
    
    except Exception as e:
        logger.exception(f"Error in scheduled audit: {str(e)}")
        
        # Try to update audit record if it was created
        try:
            if audit_id:
                audit = SystemAudit.query.get(audit_id)
                if audit:
                    audit.status = 'error'
                    audit.summary = f"Audit failed due to error: {str(e)}"
                    audit.completed_at = datetime.utcnow()
                    db.session.commit()
        except:
            logger.exception("Error updating audit record after failure")
        
        # Log error
        audit_service.log_activity(
            user_id=None, 
            action='error',
            resource_type='scheduled_audit',
            resource_id=audit_id if 'audit_id' in locals() else None,
            description=f"Scheduled audit failed: {str(e)}",
            status='failure'
        )
        
        return False, f"Audit failed: {str(e)}", audit_id if 'audit_id' in locals() else None

def perform_code_quality_audit(audit_id):
    """
    Perform code quality analysis
    
    Args:
        audit_id: ID of the audit record
        
    Returns:
        tuple: (results_dict, findings_list)
    """
    results = {}
    findings = []
    
    try:
        # Initialize code analyzer
        analyzer = CodeAnalyzer()
        
        # Run code analysis
        analysis_result = analyzer.analyze_project()
        
        # Extract results
        issues = analysis_result.get_summary()
        
        # Record metrics
        results = {
            'files_analyzed': issues.get('total_files', 0),
            'issues_found': issues.get('total_issues', 0),
            'critical_issues': issues.get('critical_count', 0),
            'high_issues': issues.get('high_count', 0),
            'medium_issues': issues.get('medium_count', 0),
            'low_issues': issues.get('low_count', 0)
        }
        
        # Create findings
        for issue in issues.get('issues', []):
            # Only create findings for medium severity and above
            if issue['severity'] in ['critical', 'high', 'medium']:
                finding = AuditFinding(
                    audit_id=audit_id,
                    title=issue['issue_type'],
                    category='code-quality',
                    description=f"Found in {issue['file_path']} at line {issue['line_number']}: {issue['description']}",
                    recommendation=issue.get('recommendation', 'Review and fix the identified issue.'),
                    severity=issue['severity'],
                    status='open',
                    details=json.dumps({
                        'file_path': issue['file_path'],
                        'line_number': issue['line_number'],
                        'issue_type': issue['issue_type']
                    })
                )
                db.session.add(finding)
                findings.append(finding)
        
        db.session.commit()
        logger.info(f"Code quality audit completed: found {len(findings)} significant issues")
        
    except Exception as e:
        logger.exception(f"Error in code quality audit: {str(e)}")
        # Create an error finding
        error_finding = AuditFinding(
            audit_id=audit_id,
            title="Code Analysis Error",
            category='code-quality',
            description=f"Failed to analyze code: {str(e)}",
            recommendation="Review error message and fix the code analyzer.",
            severity='medium',
            status='open',
            details=json.dumps({
                'error': str(e),
                'traceback': traceback.format_exc()
            })
        )
        db.session.add(error_finding)
        findings.append(error_finding)
        db.session.commit()
        
        results = {
            'error': str(e),
            'files_analyzed': 0,
            'issues_found': 1
        }
    
    return results, findings

def perform_system_health_audit(audit_id):
    """
    Perform system health audit
    
    Args:
        audit_id: ID of the audit record
        
    Returns:
        tuple: (results_dict, findings_list)
    """
    results = {}
    findings = []
    
    try:
        # Initialize system auditor
        auditor = SystemAuditor()
        
        # Run system audit
        audit_result = auditor.audit_system()
        
        # Extract results
        checks = audit_result.get_results()
        
        # Record metrics
        results = {
            'cpu_usage': checks.get('cpu_usage', 0),
            'memory_usage': checks.get('memory_usage', 0),
            'disk_usage': checks.get('disk_usage', 0),
            'database_connection': checks.get('database_connection', 'unknown'),
            'response_time': checks.get('response_time', 0),
            'issues_found': len(checks.get('issues', []))
        }
        
        # Create findings
        for issue in checks.get('issues', []):
            finding = AuditFinding(
                audit_id=audit_id,
                title=issue['title'],
                category='system-health',
                description=issue['description'],
                recommendation=issue.get('recommendation', 'Review system health metrics.'),
                severity=issue['severity'],
                status='open',
                details=json.dumps({
                    'component': issue.get('component', 'unknown'),
                    'metric': issue.get('metric', 'unknown'),
                    'value': issue.get('value', 'unknown'),
                    'threshold': issue.get('threshold', 'unknown')
                })
            )
            db.session.add(finding)
            findings.append(finding)
        
        db.session.commit()
        logger.info(f"System health audit completed: found {len(findings)} issues")
        
    except Exception as e:
        logger.exception(f"Error in system health audit: {str(e)}")
        # Create an error finding
        error_finding = AuditFinding(
            audit_id=audit_id,
            title="System Health Audit Error",
            category='system-health',
            description=f"Failed to analyze system health: {str(e)}",
            recommendation="Review error message and fix the system health monitor.",
            severity='medium',
            status='open',
            details=json.dumps({
                'error': str(e),
                'traceback': traceback.format_exc()
            })
        )
        db.session.add(error_finding)
        findings.append(error_finding)
        db.session.commit()
        
        results = {
            'error': str(e),
            'issues_found': 1
        }
    
    return results, findings

def perform_database_audit(audit_id):
    """
    Perform database audit
    
    Args:
        audit_id: ID of the audit record
        
    Returns:
        tuple: (results_dict, findings_list)
    """
    results = {}
    findings = []
    
    try:
        # Basic database health checks
        # Note: This would be expanded in a real implementation
        connection_success = True
        try:
            # Try a simple query
            db.session.execute("SELECT 1").fetchone()
        except SQLAlchemyError as e:
            connection_success = False
            db_error = str(e)
        
        # Database size/record counts (demo simplified)
        table_counts = {}
        for table_name in ['users', 'accounts', 'transactions', 'audit_logs']:
            try:
                count = db.session.execute(f"SELECT COUNT(*) FROM {table_name}").scalar()
                table_counts[table_name] = count
            except SQLAlchemyError:
                table_counts[table_name] = "error"
        
        # Record metrics
        results = {
            'connection_success': connection_success,
            'error': None if connection_success else db_error,
            'table_counts': table_counts
        }
        
        # Create findings for database issues
        if not connection_success:
            finding = AuditFinding(
                audit_id=audit_id,
                title="Database Connection Failure",
                category='database',
                description=f"Failed to connect to database: {db_error}",
                recommendation="Check database connection settings and ensure database is running.",
                severity='critical',
                status='open',
                details=json.dumps({
                    'error': db_error
                })
            )
            db.session.add(finding)
            findings.append(finding)
        
        db.session.commit()
        logger.info(f"Database audit completed: found {len(findings)} issues")
        
    except Exception as e:
        logger.exception(f"Error in database audit: {str(e)}")
        # Create an error finding
        error_finding = AuditFinding(
            audit_id=audit_id,
            title="Database Audit Error",
            category='database',
            description=f"Failed to perform database audit: {str(e)}",
            recommendation="Review error message and fix the database audit module.",
            severity='medium',
            status='open',
            details=json.dumps({
                'error': str(e),
                'traceback': traceback.format_exc()
            })
        )
        db.session.add(error_finding)
        findings.append(error_finding)
        db.session.commit()
        
        results = {
            'error': str(e),
            'issues_found': 1
        }
    
    return results, findings

def get_eastern_time(datetime_obj=None):
    """Convert UTC time to Eastern Time"""
    eastern = pytz.timezone('US/Eastern')
    if datetime_obj is None:
        datetime_obj = datetime.utcnow()
    
    if datetime_obj.tzinfo is None:
        datetime_obj = pytz.utc.localize(datetime_obj)
        
    return datetime_obj.astimezone(eastern)