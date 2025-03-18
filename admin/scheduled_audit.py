"""
Scheduled System Audit Module

Provides automated system health checks and code quality analysis.
Runs daily at 8:00 PM ET to identify issues before they impact users.
"""

import logging
import json
import os
import psutil
import datetime
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError
import traceback
import hashlib
import re
import pytz
import sys
import time
from pathlib import Path

from models import db, SystemAudit, AuditFinding, ErrorLog, ScheduledJob
from utils.audit_service import AuditService
from utils.code_analyzer import CodeAnalyzer
from utils.system_auditor import SystemAuditor
from utils.scheduler import get_eastern_time

logger = logging.getLogger(__name__)

class ScheduledAuditService:
    """
    Service to run scheduled system audits
    
    This class handles the execution of comprehensive system health checks and code quality analysis
    on a scheduled basis (daily at 8:00 PM ET).
    """
    
    def __init__(self):
        """Initialize audit service with configuration"""
        self.code_analyzer = CodeAnalyzer()
        self.system_auditor = SystemAuditor()
        self.audit_service = AuditService()
        self.audit_types = ['security', 'performance', 'data-integrity', 'code-quality']
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.admin_user_id = self._get_admin_user_id()
        self.job_id = 'daily_system_audit'
        
    def _get_admin_user_id(self):
        """Get the admin user ID for audit attribution"""
        try:
            from models import User
            admin = User.query.filter_by(is_admin=True).first()
            return admin.id if admin else None
        except Exception as e:
            logger.error(f"Failed to get admin user ID: {e}")
            return None
        
    def _update_job_status(self, status, error=None):
        """Update the scheduled job status in the database"""
        try:
            job = ScheduledJob.query.filter_by(job_id=self.job_id).first()
            
            if not job:
                job = ScheduledJob(
                    job_id=self.job_id,
                    description="Daily system audit at 8:00 PM ET",
                    enabled=True
                )
                db.session.add(job)
            
            job.last_run = datetime.datetime.utcnow()
            job.last_status = status
            
            if status == 'success':
                job.success_count += 1
                job.last_error = None
            else:
                job.error_count += 1
                job.last_error = str(error) if error else "Unknown error"
                
            db.session.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update job status: {e}")
            return False
        
    def run_daily_audit(self):
        """
        Execute daily system audit
        
        This method runs all configured audit types and stores results in the database
        """
        logger.info("Starting daily system audit")
        start_time = time.time()
        
        try:
            # Create a root audit record
            system_audit = SystemAudit(
                audit_type='system-daily',
                status='in_progress',
                summary='Daily system audit in progress',
                performed_by=self.admin_user_id
            )
            db.session.add(system_audit)
            db.session.commit()
            audit_id = system_audit.id
            
            # Run individual audit types
            audit_results = {}
            has_critical_findings = False
            
            for audit_type in self.audit_types:
                try:
                    if audit_type == 'security':
                        result = self._run_security_audit(audit_id)
                    elif audit_type == 'performance':
                        result = self._run_performance_audit(audit_id)
                    elif audit_type == 'data-integrity':
                        result = self._run_data_integrity_audit(audit_id)
                    elif audit_type == 'code-quality':
                        result = self._run_code_quality_audit(audit_id)
                    else:
                        result = {
                            'status': 'skipped',
                            'summary': f"Unknown audit type: {audit_type}",
                            'findings': []
                        }
                        
                    audit_results[audit_type] = result
                    
                    # Check if this audit has critical findings
                    if result.get('status') == 'failed' or any(f.get('severity') == 'critical' for f in result.get('findings', [])):
                        has_critical_findings = True
                        
                except Exception as e:
                    logger.error(f"Error running {audit_type} audit: {e}")
                    audit_results[audit_type] = {
                        'status': 'error',
                        'summary': f"Error running audit: {str(e)}",
                        'error': str(e),
                        'findings': []
                    }
            
            # Calculate duration and update the root audit record
            duration = time.time() - start_time
            overall_status = 'failed' if has_critical_findings else 'passed'
            
            # Update the root audit record
            system_audit = SystemAudit.query.get(audit_id)
            system_audit.status = overall_status
            system_audit.summary = self._generate_summary(audit_results)
            system_audit.details = json.dumps(audit_results)
            system_audit.duration = duration
            
            db.session.commit()
            
            # Update job status
            self._update_job_status('success')
            
            logger.info(f"Daily system audit completed with status: {overall_status}")
            return {
                'status': 'success',
                'audit_id': audit_id,
                'summary': system_audit.summary
            }
            
        except Exception as e:
            logger.error(f"Error running daily system audit: {e}")
            error_details = traceback.format_exc()
            
            try:
                # If we already created the audit record, update it
                if 'audit_id' in locals():
                    system_audit = SystemAudit.query.get(audit_id)
                    if system_audit:
                        system_audit.status = 'error'
                        system_audit.summary = f"Error running daily audit: {str(e)}"
                        system_audit.details = json.dumps({
                            'error': str(e),
                            'traceback': error_details
                        })
                        db.session.commit()
            except Exception as db_error:
                logger.error(f"Error updating audit record: {db_error}")
                
            # Log error
            ErrorLog.log_error(
                'scheduled_audit',
                str(e),
                error_details,
                user_id=self.admin_user_id
            )
            
            # Update job status
            self._update_job_status('failed', error=e)
            
            return {
                'status': 'error',
                'error': str(e)
            }
            
    def _generate_summary(self, audit_results):
        """Generate an overall summary of audit results"""
        total_findings = 0
        critical_findings = 0
        high_findings = 0
        passed_audits = 0
        failed_audits = 0
        
        for audit_type, result in audit_results.items():
            if result.get('status') == 'passed':
                passed_audits += 1
            elif result.get('status') == 'failed':
                failed_audits += 1
                
            for finding in result.get('findings', []):
                total_findings += 1
                if finding.get('severity') == 'critical':
                    critical_findings += 1
                elif finding.get('severity') == 'high':
                    high_findings += 1
        
        summary = f"System Audit Summary: {passed_audits} passed, {failed_audits} failed. "
        if total_findings > 0:
            summary += f"Found {total_findings} issues ({critical_findings} critical, {high_findings} high priority)."
        else:
            summary += "No issues found."
            
        return summary
    
    def _run_security_audit(self, parent_audit_id):
        """Run security-focused audit checks"""
        logger.info("Running security audit")
        
        # Create audit record
        audit = SystemAudit(
            audit_type='security',
            status='in_progress',
            summary='Security audit in progress',
            performed_by=self.admin_user_id
        )
        db.session.add(audit)
        db.session.commit()
        
        try:
            # Run security checks
            security_results = self.system_auditor.check_security()
            findings = []
            
            # Process findings
            for check_name, check_result in security_results.items():
                if not check_result.get('passed', True):
                    finding = AuditFinding(
                        audit_id=audit.id,
                        category='security',
                        severity=check_result.get('severity', 'medium'),
                        title=check_name,
                        description=check_result.get('description', ''),
                        recommendation=check_result.get('recommendation', ''),
                        status='open',
                        details=json.dumps(check_result.get('details', {}))
                    )
                    db.session.add(finding)
                    findings.append({
                        'severity': finding.severity,
                        'title': finding.title,
                        'description': finding.description
                    })
            
            # Determine overall status
            has_critical = any(f.get('severity') == 'critical' for f in findings)
            status = 'failed' if has_critical else 'warning' if findings else 'passed'
            
            # Update audit record
            audit.status = status
            audit.summary = f"Security audit completed with status: {status}. Found {len(findings)} issues."
            audit.details = json.dumps(security_results)
            db.session.commit()
            
            return {
                'status': status,
                'summary': audit.summary,
                'findings': findings
            }
            
        except Exception as e:
            logger.error(f"Error in security audit: {e}")
            error_details = traceback.format_exc()
            
            # Update audit record
            audit.status = 'error'
            audit.summary = f"Error in security audit: {str(e)}"
            audit.details = json.dumps({
                'error': str(e),
                'traceback': error_details
            })
            db.session.commit()
            
            return {
                'status': 'error',
                'summary': audit.summary,
                'error': str(e),
                'findings': []
            }
    
    def _run_performance_audit(self, parent_audit_id):
        """Run performance-focused audit checks"""
        logger.info("Running performance audit")
        
        # Create audit record
        audit = SystemAudit(
            audit_type='performance',
            status='in_progress',
            summary='Performance audit in progress',
            performed_by=self.admin_user_id
        )
        db.session.add(audit)
        db.session.commit()
        
        try:
            # Run performance checks
            performance_results = self.system_auditor.check_performance()
            findings = []
            
            # Process findings
            for check_name, check_result in performance_results.items():
                if not check_result.get('passed', True):
                    finding = AuditFinding(
                        audit_id=audit.id,
                        category='performance',
                        severity=check_result.get('severity', 'medium'),
                        title=check_name,
                        description=check_result.get('description', ''),
                        recommendation=check_result.get('recommendation', ''),
                        status='open',
                        details=json.dumps(check_result.get('details', {}))
                    )
                    db.session.add(finding)
                    findings.append({
                        'severity': finding.severity,
                        'title': finding.title,
                        'description': finding.description
                    })
            
            # Determine overall status
            has_critical = any(f.get('severity') == 'critical' for f in findings)
            status = 'failed' if has_critical else 'warning' if findings else 'passed'
            
            # Update audit record
            audit.status = status
            audit.summary = f"Performance audit completed with status: {status}. Found {len(findings)} issues."
            audit.details = json.dumps(performance_results)
            db.session.commit()
            
            return {
                'status': status,
                'summary': audit.summary,
                'findings': findings
            }
            
        except Exception as e:
            logger.error(f"Error in performance audit: {e}")
            error_details = traceback.format_exc()
            
            # Update audit record
            audit.status = 'error'
            audit.summary = f"Error in performance audit: {str(e)}"
            audit.details = json.dumps({
                'error': str(e),
                'traceback': error_details
            })
            db.session.commit()
            
            return {
                'status': 'error',
                'summary': audit.summary,
                'error': str(e),
                'findings': []
            }
    
    def _run_data_integrity_audit(self, parent_audit_id):
        """Run data integrity-focused audit checks"""
        logger.info("Running data integrity audit")
        
        # Create audit record
        audit = SystemAudit(
            audit_type='data-integrity',
            status='in_progress',
            summary='Data integrity audit in progress',
            performed_by=self.admin_user_id
        )
        db.session.add(audit)
        db.session.commit()
        
        try:
            # Run data integrity checks
            integrity_results = self.system_auditor.check_data_integrity()
            findings = []
            
            # Process findings
            for check_name, check_result in integrity_results.items():
                if not check_result.get('passed', True):
                    finding = AuditFinding(
                        audit_id=audit.id,
                        category='data-integrity',
                        severity=check_result.get('severity', 'medium'),
                        title=check_name,
                        description=check_result.get('description', ''),
                        recommendation=check_result.get('recommendation', ''),
                        status='open',
                        details=json.dumps(check_result.get('details', {}))
                    )
                    db.session.add(finding)
                    findings.append({
                        'severity': finding.severity,
                        'title': finding.title,
                        'description': finding.description
                    })
            
            # Determine overall status
            has_critical = any(f.get('severity') == 'critical' for f in findings)
            status = 'failed' if has_critical else 'warning' if findings else 'passed'
            
            # Update audit record
            audit.status = status
            audit.summary = f"Data integrity audit completed with status: {status}. Found {len(findings)} issues."
            audit.details = json.dumps(integrity_results)
            db.session.commit()
            
            return {
                'status': status,
                'summary': audit.summary,
                'findings': findings
            }
            
        except Exception as e:
            logger.error(f"Error in data integrity audit: {e}")
            error_details = traceback.format_exc()
            
            # Update audit record
            audit.status = 'error'
            audit.summary = f"Error in data integrity audit: {str(e)}"
            audit.details = json.dumps({
                'error': str(e),
                'traceback': error_details
            })
            db.session.commit()
            
            return {
                'status': 'error',
                'summary': audit.summary,
                'error': str(e),
                'findings': []
            }
    
    def _run_code_quality_audit(self, parent_audit_id):
        """Run code quality-focused audit checks"""
        logger.info("Running code quality audit")
        
        # Create audit record
        audit = SystemAudit(
            audit_type='code-quality',
            status='in_progress',
            summary='Code quality audit in progress',
            performed_by=self.admin_user_id
        )
        db.session.add(audit)
        db.session.commit()
        
        try:
            # Run code analysis
            result = self.code_analyzer.analyze_project(self.root_dir)
            findings = []
            
            # Process findings
            for issue in result.issues:
                finding = AuditFinding(
                    audit_id=audit.id,
                    category='code-quality',
                    severity=issue.severity,
                    title=f"{issue.issue_type} in {os.path.basename(issue.file_path)}",
                    description=issue.description,
                    recommendation=issue.recommendation,
                    status='open',
                    details=json.dumps({
                        'file_path': issue.file_path,
                        'line_number': issue.line_number,
                        'issue_type': issue.issue_type
                    })
                )
                db.session.add(finding)
                findings.append({
                    'severity': finding.severity,
                    'title': finding.title,
                    'description': finding.description
                })
            
            # Determine overall status
            has_critical = any(f.get('severity') == 'critical' for f in findings)
            status = 'failed' if has_critical else 'warning' if findings else 'passed'
            
            # Update audit record
            audit.status = status
            audit.summary = f"Code quality audit completed with status: {status}. Found {len(findings)} issues."
            audit.details = json.dumps(result.get_summary())
            db.session.commit()
            
            return {
                'status': status,
                'summary': audit.summary,
                'findings': findings
            }
            
        except Exception as e:
            logger.error(f"Error in code quality audit: {e}")
            error_details = traceback.format_exc()
            
            # Update audit record
            audit.status = 'error'
            audit.summary = f"Error in code quality audit: {str(e)}"
            audit.details = json.dumps({
                'error': str(e),
                'traceback': error_details
            })
            db.session.commit()
            
            return {
                'status': 'error',
                'summary': audit.summary,
                'error': str(e),
                'findings': []
            }

def configure_scheduled_audit(scheduler):
    """
    Configure the scheduled audit job
    
    Args:
        scheduler: APScheduler instance to register the job with
    """
    audit_service = ScheduledAuditService()
    
    # Schedule daily job at 8:00 PM ET
    eastern = pytz.timezone('US/Eastern')
    scheduler.add_job(
        audit_service.run_daily_audit,
        'cron',
        hour=20,  # 8:00 PM
        minute=0,
        timezone=eastern,
        id='daily_system_audit',
        replace_existing=True,
        name='Daily System Audit'
    )
    
    logger.info("Scheduled daily audit configured for 8:00 PM ET")
    
    return True