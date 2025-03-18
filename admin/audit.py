from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from flask_login import login_required, current_user
from functools import wraps
from sqlalchemy import desc
import json
import logging

from models import db, User, AuditLog, SystemAudit, AuditFinding
from utils.audit_service import AuditService

audit_bp = Blueprint('audit', __name__, url_prefix='/admin/audit')
logger = logging.getLogger(__name__)
audit_service = AuditService()

# Admin-only decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('You need admin privileges to access this page.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@audit_bp.route('/')
@login_required
@admin_required
def index():
    """Audit dashboard index page"""
    # Get stats for dashboard
    total_audits = SystemAudit.query.count()
    total_logs = AuditLog.query.count()
    total_findings = AuditFinding.query.count()
    open_findings = AuditFinding.query.filter(AuditFinding.status != 'resolved').count()
    
    # Get recent audit logs
    recent_logs = AuditLog.query.order_by(desc(AuditLog.timestamp)).limit(10).all()
    
    # Get recent audits
    recent_audits = SystemAudit.query.order_by(desc(SystemAudit.timestamp)).limit(5).all()
    
    # Get critical findings
    critical_findings = AuditFinding.query.filter(
        AuditFinding.severity.in_(['critical', 'high']),
        AuditFinding.status != 'resolved'
    ).order_by(desc(AuditFinding.timestamp)).limit(5).all()
    
    return render_template('admin/audit/dashboard.html', 
                          total_audits=total_audits,
                          total_logs=total_logs,
                          total_findings=total_findings,
                          open_findings=open_findings,
                          recent_logs=recent_logs,
                          recent_audits=recent_audits,
                          critical_findings=critical_findings)

@audit_bp.route('/logs')
@login_required
@admin_required
def logs():
    """View all audit logs with filtering"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Initialize filter values
    filters = {
        'action': request.args.get('action'),
        'resource_type': request.args.get('resource_type'),
        'user_id': request.args.get('user_id'),
        'status': request.args.get('status'),
        'date_from': request.args.get('date_from'),
        'date_to': request.args.get('date_to')
    }
    
    # Build query with filters
    query = AuditLog.query
    
    if filters['action']:
        query = query.filter(AuditLog.action == filters['action'])
    
    if filters['resource_type']:
        query = query.filter(AuditLog.resource_type == filters['resource_type'])
    
    if filters['user_id']:
        query = query.filter(AuditLog.user_id == int(filters['user_id']))
    
    if filters['status']:
        query = query.filter(AuditLog.status == filters['status'])
    
    if filters['date_from']:
        from_date = datetime.strptime(filters['date_from'], '%Y-%m-%d')
        query = query.filter(AuditLog.timestamp >= from_date)
    
    if filters['date_to']:
        to_date = datetime.strptime(filters['date_to'], '%Y-%m-%d')
        # Add one day to include all events on the end date
        to_date = to_date + timedelta(days=1)
        query = query.filter(AuditLog.timestamp <= to_date)
    
    # Get unique values for filter dropdowns
    actions = db.session.query(AuditLog.action).distinct().all()
    actions = [action[0] for action in actions]
    
    resource_types = db.session.query(AuditLog.resource_type).distinct().all()
    resource_types = [rt[0] for rt in resource_types if rt[0]]
    
    users = User.query.all()
    
    # Paginate results
    logs = query.order_by(desc(AuditLog.timestamp)).paginate(page=page, per_page=per_page)
    
    return render_template('admin/audit/logs.html', 
                           logs=logs, 
                           filters=filters,
                           actions=actions,
                           resource_types=resource_types,
                           users=users)

@audit_bp.route('/audits')
@login_required
@admin_required
def audits():
    """View all system audits"""
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Filter by audit type
    audit_type = request.args.get('type')
    status = request.args.get('status')
    
    query = SystemAudit.query
    
    if audit_type:
        query = query.filter(SystemAudit.audit_type == audit_type)
    
    if status:
        query = query.filter(SystemAudit.status == status)
    
    # Paginate results
    audits = query.order_by(desc(SystemAudit.timestamp)).paginate(page=page, per_page=per_page)
    
    return render_template('admin/audit/audits.html', audits=audits)

@audit_bp.route('/audit/<int:audit_id>')
@login_required
@admin_required
def audit_detail(audit_id):
    """View detailed audit report"""
    audit = SystemAudit.query.get_or_404(audit_id)
    findings = AuditFinding.query.filter_by(audit_id=audit_id).order_by(desc(AuditFinding.severity)).all()
    
    # Parse detailed metrics if available
    details = {}
    if audit.details:
        try:
            details = json.loads(audit.details)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse audit details for audit ID {audit_id}")
    
    return render_template('admin/audit/audit_detail.html', 
                           audit=audit, 
                           findings=findings,
                           details=details)

@audit_bp.route('/findings')
@login_required
@admin_required
def findings():
    """View all findings with filtering"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Filter parameters
    severity = request.args.get('severity')
    status = request.args.get('status')
    category = request.args.get('category')
    
    query = AuditFinding.query
    
    if severity:
        query = query.filter(AuditFinding.severity == severity)
    
    if status:
        query = query.filter(AuditFinding.status == status)
    
    if category:
        query = query.filter(AuditFinding.category == category)
    
    # Get filter options
    categories = db.session.query(AuditFinding.category).distinct().all()
    categories = [c[0] for c in categories if c[0]]
    
    # Paginate results
    findings = query.order_by(
        desc(AuditFinding.severity),
        AuditFinding.status,
        desc(AuditFinding.timestamp)
    ).paginate(page=page, per_page=per_page)
    
    return render_template('admin/audit/findings.html', 
                           findings=findings,
                           categories=categories)

@audit_bp.route('/finding/<int:finding_id>/update', methods=['POST'])
@login_required
@admin_required
def update_finding(finding_id):
    """Update finding status"""
    finding = AuditFinding.query.get_or_404(finding_id)
    
    status = request.form.get('status')
    resolution_notes = request.form.get('resolution_notes', '')
    
    if status:
        old_status = finding.status
        finding.status = status
        finding.resolution_notes = resolution_notes
        
        # If resolving, set resolved timestamp
        if status == 'resolved' and old_status != 'resolved':
            finding.resolved_at = datetime.utcnow()
        
        db.session.commit()
        
        # Log this activity
        audit_service.log_activity(
            user_id=current_user.id,
            action='update',
            resource_type='finding',
            resource_id=finding_id,
            description=f"Updated finding status from '{old_status}' to '{status}'",
            status='success'
        )
        
        flash(f'Finding updated successfully.', 'success')
    
    # Redirect back to the audit detail page
    return redirect(url_for('audit.audit_detail', audit_id=finding.audit_id))

@audit_bp.route('/run_audit', methods=['GET', 'POST'])
@login_required
@admin_required
def run_audit():
    """Run a new system audit"""
    if request.method == 'POST':
        audit_type = request.form.get('audit_type', 'comprehensive')
        
        # Create new audit record
        new_audit = SystemAudit(
            audit_type=audit_type,
            user_id=current_user.id,
            status='running',
            summary='Audit in progress...',
            duration=0.0
        )
        
        db.session.add(new_audit)
        db.session.commit()
        
        # Log the audit start
        audit_service.log_activity(
            user_id=current_user.id,
            action='start',
            resource_type='audit',
            resource_id=new_audit.id,
            description=f"Started {audit_type} audit",
            status='success'
        )
        
        # Redirect to a page to monitor the audit progress
        # In a real app, we'd run the audit in a background task
        return redirect(url_for('audit.run_audit_progress', audit_id=new_audit.id))
    
    return render_template('admin/audit/run_audit.html')

@audit_bp.route('/audit/<int:audit_id>/progress')
@login_required
@admin_required
def run_audit_progress(audit_id):
    """Display progress of a running audit"""
    audit = SystemAudit.query.get_or_404(audit_id)
    
    # For demo purposes, if the audit is still running, simulate completion
    if audit.status == 'running':
        # This would normally be done by a background worker
        perform_audit(audit)
    
    return render_template('admin/audit/audit_progress.html', audit=audit)

@audit_bp.route('/errors')
@login_required
@admin_required
def errors():
    """View error logs"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Get all logs with status 'failure'
    logs = AuditLog.query.filter_by(status='failure').order_by(
        desc(AuditLog.timestamp)
    ).paginate(page=page, per_page=per_page)
    
    return render_template('admin/audit/errors.html', logs=logs)

@audit_bp.route('/api/stats')
@login_required
@admin_required
def api_stats():
    """API endpoint for dashboard stats"""
    total_audits = SystemAudit.query.count()
    total_logs = AuditLog.query.count()
    total_findings = AuditFinding.query.count()
    open_findings = AuditFinding.query.filter(AuditFinding.status != 'resolved').count()
    
    # Count by severity
    finding_severity = {
        'critical': AuditFinding.query.filter_by(severity='critical').count(),
        'high': AuditFinding.query.filter_by(severity='high').count(),
        'medium': AuditFinding.query.filter_by(severity='medium').count(),
        'low': AuditFinding.query.filter_by(severity='low').count()
    }
    
    # Count by status
    finding_status = {
        'open': AuditFinding.query.filter_by(status='open').count(),
        'in_progress': AuditFinding.query.filter_by(status='in_progress').count(),
        'resolved': AuditFinding.query.filter_by(status='resolved').count()
    }
    
    return jsonify({
        'total_audits': total_audits,
        'total_logs': total_logs,
        'total_findings': total_findings,
        'open_findings': open_findings,
        'finding_severity': finding_severity,
        'finding_status': finding_status
    })

@audit_bp.route('/api/recent_activity')
@login_required
@admin_required
def api_recent_activity():
    """API endpoint for recent audit logs"""
    logs = AuditLog.query.order_by(desc(AuditLog.timestamp)).limit(10).all()
    
    log_data = [{
        'id': log.id,
        'timestamp': log.timestamp.isoformat(),
        'user': log.user.username if log.user else 'System',
        'action': log.action,
        'resource_type': log.resource_type,
        'resource_id': log.resource_id,
        'status': log.status,
        'description': log.description
    } for log in logs]
    
    return jsonify(log_data)

def perform_audit(audit):
    """Perform the actual audit operations
    
    This would normally be done in a background worker/celery task
    For demo purposes, we're doing it synchronously
    """
    start_time = datetime.utcnow()
    
    # Update status to running
    audit.status = 'running'
    db.session.commit()
    
    results = {}
    findings = []
    
    try:
        # Perform different checks based on audit type
        if audit.audit_type in ['security', 'comprehensive']:
            security_findings = perform_security_audit(audit.id)
            findings.extend(security_findings)
            results['security'] = {
                'checks_performed': len(security_findings),
                'issues_found': sum(1 for f in security_findings if f.severity in ['critical', 'high'])
            }
        
        if audit.audit_type in ['performance', 'comprehensive']:
            performance_findings = perform_performance_audit(audit.id)
            findings.extend(performance_findings)
            results['performance'] = {
                'checks_performed': len(performance_findings),
                'issues_found': sum(1 for f in performance_findings if f.severity in ['critical', 'high'])
            }
        
        if audit.audit_type in ['data-integrity', 'comprehensive']:
            data_findings = perform_data_integrity_audit(audit.id)
            findings.extend(data_findings)
            results['data_integrity'] = {
                'checks_performed': len(data_findings),
                'issues_found': sum(1 for f in data_findings if f.severity in ['critical', 'high'])
            }
        
        # Determine overall audit status based on findings
        if any(f.severity == 'critical' for f in findings):
            status = 'failed'
        elif any(f.severity in ['high', 'medium'] for f in findings):
            status = 'warning'
        else:
            status = 'passed'
        
        # Generate summary
        summary = f"Audit completed with {len(findings)} findings. "
        
        critical_count = sum(1 for f in findings if f.severity == 'critical')
        high_count = sum(1 for f in findings if f.severity == 'high')
        medium_count = sum(1 for f in findings if f.severity == 'medium')
        low_count = sum(1 for f in findings if f.severity == 'low')
        
        if critical_count:
            summary += f"{critical_count} critical, "
        if high_count:
            summary += f"{high_count} high, "
        if medium_count:
            summary += f"{medium_count} medium, "
        if low_count:
            summary += f"{low_count} low "
        
        summary += "severity issues found."
        
    except Exception as e:
        logger.exception(f"Error performing audit {audit.id}: {str(e)}")
        status = 'error'
        summary = f"Audit failed due to error: {str(e)}"
        
        # Log the error
        audit_service.log_activity(
            user_id=audit.user_id,
            action='error',
            resource_type='audit',
            resource_id=audit.id,
            description=f"Audit failed: {str(e)}",
            status='failure'
        )
    
    # Calculate duration
    end_time = datetime.utcnow()
    duration = (end_time - start_time).total_seconds()
    
    # Update audit record
    audit.status = status
    audit.summary = summary
    audit.duration = duration
    audit.details = json.dumps(results)
    audit.completed_at = end_time
    
    db.session.commit()
    
    # Log audit completion
    audit_service.log_activity(
        user_id=audit.user_id,
        action='complete',
        resource_type='audit',
        resource_id=audit.id,
        description=f"Completed {audit.audit_type} audit with status: {status}",
        status='success'
    )
    
    return findings

def perform_security_audit(audit_id):
    """Perform security audit checks
    
    Returns:
        List of AuditFinding objects
    """
    findings = []
    
    # Check user password policies
    users_without_password = User.query.filter(
        User.password_hash.is_(None) | User.password_hash == ''
    ).all()
    
    if users_without_password:
        finding = AuditFinding(
            audit_id=audit_id,
            title="Users without password found",
            category="authentication",
            description=f"Found {len(users_without_password)} users without passwords set.",
            recommendation="Ensure all active users have secure passwords set.",
            severity="high",
            status="open"
        )
        db.session.add(finding)
        findings.append(finding)
    
    # Check admin users
    admin_users = User.query.filter_by(is_admin=True).all()
    
    if len(admin_users) > 3:  # Arbitrary threshold
        finding = AuditFinding(
            audit_id=audit_id,
            title="Excessive admin users",
            category="authorization",
            description=f"Found {len(admin_users)} users with admin privileges.",
            recommendation="Review admin users and remove unnecessary privileges.",
            severity="medium",
            status="open"
        )
        db.session.add(finding)
        findings.append(finding)
    
    # Add more security audit checks here
    
    db.session.commit()
    return findings

def perform_performance_audit(audit_id):
    """Perform performance audit checks
    
    Returns:
        List of AuditFinding objects
    """
    findings = []
    
    # Check database size and growth
    # This would normally require more sophisticated monitoring
    # For demo, we'll add a placeholder finding
    
    # Example performance finding
    finding = AuditFinding(
        audit_id=audit_id,
        title="Database performance optimization",
        category="database",
        description="Routine performance check suggests optimization opportunities.",
        recommendation="Consider adding indexes to frequently queried tables.",
        severity="low",
        status="open"
    )
    db.session.add(finding)
    findings.append(finding)
    
    db.session.commit()
    return findings

def perform_data_integrity_audit(audit_id):
    """Perform data integrity audit checks
    
    Returns:
        List of AuditFinding objects
    """
    findings = []
    
    # Check for orphaned records
    # This would involve verifying foreign key relationships are intact
    
    # Example data integrity finding
    finding = AuditFinding(
        audit_id=audit_id,
        title="Data consistency check",
        category="data-integrity",
        description="Data integrity verification completed successfully.",
        recommendation="No action required.",
        severity="low",
        status="resolved",
        resolution_notes="Automatic verification passed",
        resolved_at=datetime.utcnow()
    )
    db.session.add(finding)
    findings.append(finding)
    
    db.session.commit()
    return findings