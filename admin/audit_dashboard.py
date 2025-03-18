"""
Admin Audit Dashboard Module

Provides comprehensive views for system audit results, findings, and scheduled jobs.
"""

import logging
import json
from datetime import datetime, timedelta
from flask import render_template, request, redirect, url_for, flash, jsonify, Blueprint
from flask_login import login_required, current_user
from sqlalchemy import desc

from models import db, SystemAudit, AuditFinding, ScheduledJob
from utils.scheduler import get_scheduled_jobs, get_eastern_time

logger = logging.getLogger(__name__)

# Create dashboard blueprint
audit_dashboard_bp = Blueprint('audit_dashboard', __name__, url_prefix='/admin/audit')

@audit_dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    """Admin audit dashboard"""
    if not current_user.is_admin:
        flash('You do not have permission to access this page', 'danger')
        return redirect(url_for('main.index'))
    
    # Get audit statistics
    audit_stats = get_audit_statistics()
    
    # Get recent audits
    recent_audits = SystemAudit.query.order_by(desc(SystemAudit.timestamp)).limit(5).all()
    
    # Get critical findings
    critical_findings = AuditFinding.query.filter_by(
        severity='critical', 
        status='open'
    ).order_by(desc(AuditFinding.timestamp)).limit(5).all()
    
    # Get scheduled jobs
    jobs = ScheduledJob.query.order_by(desc(ScheduledJob.updated_at)).all()
    
    return render_template('admin/audit/dashboard.html',
                          stats=audit_stats,
                          recent_audits=recent_audits,
                          critical_findings=critical_findings,
                          jobs=jobs,
                          title='Audit Dashboard')

@audit_dashboard_bp.route('/audits')
@login_required
def audits():
    """Admin audit list view"""
    if not current_user.is_admin:
        flash('You do not have permission to access this page', 'danger')
        return redirect(url_for('main.index'))
    
    # Get filter parameters
    audit_type = request.args.get('type', '')
    status = request.args.get('status', '')
    days = request.args.get('days', 30, type=int)
    
    # Build query
    query = SystemAudit.query
    
    if audit_type:
        query = query.filter(SystemAudit.audit_type == audit_type)
    
    if status:
        query = query.filter(SystemAudit.status == status)
    
    if days:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        query = query.filter(SystemAudit.timestamp >= cutoff_date)
    
    # Execute query with sorting
    audits = query.order_by(desc(SystemAudit.timestamp)).all()
    
    # Get audit types and statuses for filters
    audit_types = db.session.query(SystemAudit.audit_type).distinct().all()
    audit_types = [t[0] for t in audit_types]
    
    audit_statuses = db.session.query(SystemAudit.status).distinct().all()
    audit_statuses = [s[0] for s in audit_statuses]
    
    return render_template('admin/audit/audits.html',
                         audits=audits,
                         audit_types=audit_types,
                         audit_statuses=audit_statuses,
                         selected_type=audit_type,
                         selected_status=status,
                         selected_days=days,
                         title='System Audits')

@audit_dashboard_bp.route('/audit/<int:audit_id>')
@login_required
def audit_detail(audit_id):
    """Admin audit detail view"""
    if not current_user.is_admin:
        flash('You do not have permission to access this page', 'danger')
        return redirect(url_for('main.index'))
    
    # Get audit
    audit = SystemAudit.query.get_or_404(audit_id)
    
    # Get findings
    findings = AuditFinding.query.filter_by(audit_id=audit_id).order_by(
        desc(AuditFinding.severity),
        desc(AuditFinding.timestamp)
    ).all()
    
    # Parse details if present
    details = {}
    if audit.details:
        try:
            details = json.loads(audit.details)
        except:
            details = {'error': 'Could not parse audit details'}
    
    return render_template('admin/audit/audit_detail.html',
                         audit=audit,
                         findings=findings,
                         details=details,
                         title=f'Audit #{audit_id}')

@audit_dashboard_bp.route('/findings')
@login_required
def findings():
    """Admin findings list view"""
    if not current_user.is_admin:
        flash('You do not have permission to access this page', 'danger')
        return redirect(url_for('main.index'))
    
    # Get filter parameters
    category = request.args.get('category', '')
    severity = request.args.get('severity', '')
    status = request.args.get('status', '')
    days = request.args.get('days', 30, type=int)
    
    # Build query
    query = AuditFinding.query
    
    if category:
        query = query.filter(AuditFinding.category == category)
    
    if severity:
        query = query.filter(AuditFinding.severity == severity)
    
    if status:
        query = query.filter(AuditFinding.status == status)
    
    if days:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        query = query.filter(AuditFinding.timestamp >= cutoff_date)
    
    # Execute query with sorting
    findings = query.order_by(
        desc(AuditFinding.severity),
        desc(AuditFinding.timestamp)
    ).all()
    
    # Get categories, severities, and statuses for filters
    categories = db.session.query(AuditFinding.category).distinct().all()
    categories = [c[0] for c in categories]
    
    severities = db.session.query(AuditFinding.severity).distinct().all()
    severities = [s[0] for s in severities]
    
    statuses = db.session.query(AuditFinding.status).distinct().all()
    statuses = [s[0] for s in statuses]
    
    return render_template('admin/audit/findings.html',
                         findings=findings,
                         categories=categories,
                         severities=severities,
                         statuses=statuses,
                         selected_category=category,
                         selected_severity=severity,
                         selected_status=status,
                         selected_days=days,
                         title='Audit Findings')

@audit_dashboard_bp.route('/finding/<int:finding_id>')
@login_required
def finding_detail(finding_id):
    """Admin finding detail view"""
    if not current_user.is_admin:
        flash('You do not have permission to access this page', 'danger')
        return redirect(url_for('main.index'))
    
    # Get finding
    finding = AuditFinding.query.get_or_404(finding_id)
    
    # Get parent audit
    audit = SystemAudit.query.get(finding.audit_id)
    
    # Parse details if present
    details = {}
    if finding.details:
        try:
            details = json.loads(finding.details)
        except:
            details = {'error': 'Could not parse finding details'}
    
    return render_template('admin/audit/finding_detail.html',
                         finding=finding,
                         audit=audit,
                         details=details,
                         title=f'Finding #{finding_id}')

@audit_dashboard_bp.route('/jobs')
@login_required
def jobs():
    """Admin scheduled jobs list view"""
    if not current_user.is_admin:
        flash('You do not have permission to access this page', 'danger')
        return redirect(url_for('main.index'))
    
    # Get jobs from database
    db_jobs = ScheduledJob.query.order_by(desc(ScheduledJob.updated_at)).all()
    
    # Get jobs from scheduler
    scheduler_jobs = get_scheduled_jobs()
    
    # Convert scheduler jobs to dictionaries for template
    scheduler_job_data = []
    for job in scheduler_jobs:
        # Get next run time in Eastern Time
        next_run = None
        if job.next_run_time:
            next_run = get_eastern_time(job.next_run_time)
        
        scheduler_job_data.append({
            'id': job.id,
            'name': job.name if hasattr(job, 'name') else job.id,
            'next_run_time': next_run,
            'trigger': str(job.trigger) if hasattr(job, 'trigger') else 'Unknown'
        })
    
    return render_template('admin/audit/jobs.html',
                         db_jobs=db_jobs,
                         scheduler_jobs=scheduler_job_data,
                         title='Scheduled Jobs')

@audit_dashboard_bp.route('/finding/<int:finding_id>/resolve', methods=['POST'])
@login_required
def resolve_finding(finding_id):
    """Mark a finding as resolved"""
    if not current_user.is_admin:
        flash('You do not have permission to access this page', 'danger')
        return redirect(url_for('main.index'))
    
    # Get finding
    finding = AuditFinding.query.get_or_404(finding_id)
    
    # Get resolution notes
    notes = request.form.get('resolution_notes', '')
    
    # Update finding
    finding.status = 'resolved'
    finding.resolved_at = datetime.utcnow()
    finding.resolution_notes = notes
    
    # Save changes
    db.session.commit()
    
    flash('Finding marked as resolved', 'success')
    return redirect(url_for('audit_dashboard.finding_detail', finding_id=finding_id))

def get_audit_statistics():
    """Get audit statistics for dashboard"""
    stats = {}
    
    # Count audits by type
    audit_types = db.session.query(
        SystemAudit.audit_type, 
        db.func.count(SystemAudit.id)
    ).group_by(SystemAudit.audit_type).all()
    
    stats['audit_types'] = dict(audit_types)
    
    # Count audits by status
    audit_statuses = db.session.query(
        SystemAudit.status, 
        db.func.count(SystemAudit.id)
    ).group_by(SystemAudit.status).all()
    
    stats['audit_statuses'] = dict(audit_statuses)
    
    # Count findings by severity
    finding_severities = db.session.query(
        AuditFinding.severity, 
        db.func.count(AuditFinding.id)
    ).group_by(AuditFinding.severity).all()
    
    stats['finding_severities'] = dict(finding_severities)
    
    # Count open findings
    open_findings = AuditFinding.query.filter_by(status='open').count()
    stats['open_findings'] = open_findings
    
    # Count resolved findings
    resolved_findings = AuditFinding.query.filter_by(status='resolved').count()
    stats['resolved_findings'] = resolved_findings
    
    # Get latest audit
    latest_audit = SystemAudit.query.order_by(desc(SystemAudit.timestamp)).first()
    stats['latest_audit'] = latest_audit
    
    # Get job statistics
    successful_jobs = ScheduledJob.query.filter_by(last_status='success').count()
    failed_jobs = ScheduledJob.query.filter_by(last_status='failed').count()
    
    stats['job_stats'] = {
        'successful': successful_jobs,
        'failed': failed_jobs,
        'total': successful_jobs + failed_jobs
    }
    
    return stats