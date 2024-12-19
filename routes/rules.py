import logging
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, current_app
from flask_login import login_required, current_user
from utils.route_protection import RouteProtection
from models import db, KeywordRule

logger = logging.getLogger(__name__)

rules = Blueprint('rules', __name__)
rules.protected_routes = True  # Enable protection for production

@rules.route('/rules/manage')
@login_required
@RouteProtection.protect_production
@RouteProtection.protect_data
def manage_rules():
    """Display rules management interface with enhanced protection"""
    try:
        # Only fetch active rules for the current user
        user_rules = KeywordRule.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).order_by(KeywordRule.priority.desc()).all()
        
        logger.info(f"Successfully retrieved rules for user {current_user.id}")
        return render_template('rules/manage.html', rules=user_rules)
    except Exception as e:
        logger.error(f"Error accessing rules for user {current_user.id}: {str(e)}")
        flash('Error accessing rules', 'error')
        return redirect(url_for('main.index'))

@rules.route('/rules/create', methods=['GET', 'POST'])
@login_required
@RouteProtection.protect_production
@RouteProtection.protect_data
def create_rule():
    """Create new rule with protection checks"""
    if request.method == 'POST':
        try:
            pattern = request.form.get('pattern')
            description = request.form.get('description')
            category = request.form.get('category')
            
            if not all([pattern, description, category]):
                flash('All fields are required', 'error')
                return redirect(url_for('rules.manage_rules'))
                
            # Create rule with protection
            new_rule = KeywordRule(
                pattern=pattern,
                description=description,
                category=category,
                user_id=current_user.id,
                is_active=True
            )
            
            db.session.add(new_rule)
            db.session.commit()
            
            flash('Rule created successfully', 'success')
            logger.info(f"New rule created by user {current_user.id}: {pattern}")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating rule: {str(e)}")
            flash('Error creating rule', 'error')
            
        return redirect(url_for('rules.manage_rules'))
        
    return render_template('rules/create.html')

@rules.route('/rules/<int:rule_id>/edit', methods=['GET', 'POST'])
@login_required
@RouteProtection.protect_production
@RouteProtection.protect_data
def edit_rule(rule_id):
    """Edit existing rule with protection"""
    rule = KeywordRule.query.get_or_404(rule_id)
    
    # Verify ownership
    if rule.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('rules.manage_rules'))
    
    if request.method == 'POST':
        try:
            rule.pattern = request.form.get('pattern')
            rule.description = request.form.get('description')
            rule.category = request.form.get('category')
            
            db.session.commit()
            flash('Rule updated successfully', 'success')
            logger.info(f"Rule {rule_id} updated by user {current_user.id}")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating rule: {str(e)}")
            flash('Error updating rule', 'error')
            
        return redirect(url_for('rules.manage_rules'))
        
    return render_template('rules/edit.html', rule=rule)

@rules.route('/rules/<int:rule_id>/toggle', methods=['POST'])
@login_required
@RouteProtection.protect_production
@RouteProtection.protect_data
def toggle_rule(rule_id):
    """Toggle rule active status with protection"""
    try:
        rule = KeywordRule.query.get_or_404(rule_id)
        
        # Verify ownership
        if rule.user_id != current_user.id:
            return jsonify({'error': 'Access denied'}), 403
            
        rule.is_active = not rule.is_active
        db.session.commit()
        
        logger.info(f"Rule {rule_id} {'activated' if rule.is_active else 'deactivated'} by user {current_user.id}")
        return jsonify({'success': True, 'is_active': rule.is_active})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error toggling rule: {str(e)}")
        return jsonify({'error': str(e)}), 500

@rules.route('/rules/<int:rule_id>/delete', methods=['POST'])
@login_required
@RouteProtection.protect_production
@RouteProtection.protect_data
def delete_rule(rule_id):
    """Delete rule with protection"""
    try:
        rule = KeywordRule.query.get_or_404(rule_id)
        
        # Verify ownership
        if rule.user_id != current_user.id:
            flash('Access denied', 'error')
            return redirect(url_for('rules.manage_rules'))
            
        db.session.delete(rule)
        db.session.commit()
        
        flash('Rule deleted successfully', 'success')
        logger.info(f"Rule {rule_id} deleted by user {current_user.id}")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting rule: {str(e)}")
        flash('Error deleting rule', 'error')
        
    return redirect(url_for('rules.manage_rules'))
