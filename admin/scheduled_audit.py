"""
Scheduled audit service for running automated system audits and code analysis
"""
import logging
import json
import traceback
from datetime import datetime
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from models import SystemAudit, AuditFinding, User, db
from utils.system_auditor import run_system_audit
from utils.code_analyzer import analyze_code
from utils.audit_service import audit_service

# Configure logging
logger = logging.getLogger(__name__)

def run_daily_audit():
    """
    Run comprehensive daily audit at 8:00 PM ET
    This function:
    1. Performs a system health check
    2. Analyses code for bugs and inefficiencies
    3. Checks for security vulnerabilities
    4. Creates a detailed audit report with findings
    """
    logger.info("Starting daily automated audit")
    
    try:
        # Record the audit start time
        start_time = datetime.utcnow()
        
        # Create an audit record
        audit = SystemAudit(
            audit_type='daily_comprehensive',
            status='running',
            summary='Automated daily audit in progress',
            timestamp=start_time,
            # No user ID since this is automated
            performed_by=None
        )
        
        db.session.add(audit)
        db.session.commit()
        audit_id = audit.id
        
        logger.info(f"Created audit record with ID: {audit_id}")
        
        # Run system audit
        system_audit_results = run_system_audit(current_app, db)
        
        # Run code analysis
        code_analysis_results = analyze_code()
        
        # Process findings from system audit
        findings_count = 0
        if 'findings' in system_audit_results:
            for finding in system_audit_results['findings']:
                # Map severity to our format
                severity_map = {
                    'critical': 'critical',
                    'high': 'high', 
                    'medium': 'medium',
                    'low': 'low',
                    'info': 'info'
                }
                
                severity = severity_map.get(finding['severity'].lower(), 'medium')
                
                # Create finding record
                audit_finding = AuditFinding(
                    audit_id=audit_id,
                    category=finding['category'],
                    severity=severity,
                    title=finding['title'],
                    description=finding['description'],
                    recommendation=finding.get('recommendation', 'No specific recommendation provided.'),
                    status='open'
                )
                
                db.session.add(audit_finding)
                findings_count += 1
        
        # Process findings from code analysis
        code_issues = code_analysis_results.get('stats', {}).get('issues_found', 0)
        severe_issues = (
            code_analysis_results.get('stats', {}).get('critical_issues', 0) +
            code_analysis_results.get('stats', {}).get('high_issues', 0)
        )
        
        # Combine results for the audit summary
        summary = (
            f"Daily automated audit completed with {findings_count} system findings and "
            f"{code_issues} code issues ({severe_issues} severe). "
            f"System CPU: {system_audit_results.get('stats', {}).get('cpu_usage', 'N/A')}%, "
            f"Memory: {system_audit_results.get('stats', {}).get('memory_usage', 'N/A')}%, "
            f"Disk: {system_audit_results.get('stats', {}).get('disk_usage', 'N/A')}%"
        )
        
        # Calculate audit duration
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        # Update the audit record
        audit.status = 'completed'
        audit.summary = summary
        audit.duration = duration
        audit.details = json.dumps({
            'system_stats': system_audit_results.get('stats', {}),
            'code_stats': code_analysis_results.get('stats', {})
        })
        
        db.session.commit()
        
        # Log the activity
        audit_service.log_activity(
            user_id=None,
            action='complete',
            resource_type='audit',
            resource_id=audit_id,
            description=f"Completed automated daily audit: {findings_count} findings",
            status='success'
        )
        
        logger.info(f"Daily audit completed successfully in {duration:.2f} seconds")
        return True, f"Audit completed with {findings_count} findings", audit_id
        
    except Exception as e:
        error_msg = f"Error during daily audit: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        
        # Try to update the audit record if it was created
        try:
            if 'audit_id' in locals():
                audit = SystemAudit.query.get(audit_id)
                if audit:
                    audit.status = 'failed'
                    audit.summary = f"Audit failed: {str(e)}"
                    db.session.commit()
                    
                    # Log the failure
                    audit_service.log_activity(
                        user_id=None,
                        action='fail',
                        resource_type='audit',
                        resource_id=audit_id,
                        description=f"Automated daily audit failed: {str(e)}",
                        status='failure'
                    )
        except Exception as commit_error:
            logger.error(f"Error updating failed audit: {str(commit_error)}")
        
        return False, error_msg, None

def register_scheduled_audits(scheduler):
    """
    Register scheduled audit jobs with the provided scheduler
    
    Args:
        scheduler: The APScheduler instance to register jobs with
    """
    try:
        # Add daily audit job at 8:00 PM Eastern Time
        scheduler.add_scheduled_job(
            id='daily_system_audit',
            func=run_daily_audit,
            trigger='cron',
            hour=20,  # 8:00 PM
            minute=0
        )
        
        logger.info("Scheduled daily system audit for 8:00 PM ET")
        return True
    except Exception as e:
        logger.error(f"Failed to register scheduled audit: {str(e)}")
        return False