import logging
from datetime import datetime
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
        # Verify environment protection
        is_production = current_app.config.get('ENV') == 'production'
        if is_production and not RouteProtection.verify_environment():
            logger.error("Production environment protection verification failed")
            flash('Enhanced protection mode is required in production', 'error')
            return redirect(url_for('main.index'))

        # Only fetch active rules for the current user
        user_rules = KeywordRule.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).order_by(KeywordRule.priority.desc()).all()
        
        # Get protected categories from config
        protected_categories = current_app.config.get('PROTECTED_CATEGORIES', [])
        
        # Get rule statistics
        stats = {
            'total_rules': len(user_rules),
            'active_rules': len([r for r in user_rules if r.is_active]),
            'protected_rules': len([r for r in user_rules if r.is_protected]),
            'regex_rules': len([r for r in user_rules if r.is_regex])
        }
        
        logger.info(f"Successfully retrieved rules for user {current_user.id}")
        return render_template('rules/manage.html',
                            rules=user_rules,
                            protected_categories=protected_categories,
                            stats=stats,
                            is_production=is_production)
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
    """Edit existing rule with enhanced protection and validation"""
    try:
        rule = KeywordRule.query.get_or_404(rule_id)
        
        # Verify ownership and protection status
        if rule.user_id != current_user.id:
            logger.warning(f"Unauthorized access attempt to rule {rule_id} by user {current_user.id}")
            flash('Access denied: You can only edit your own rules', 'error')
            return redirect(url_for('rules.manage_rules'))
        
        # Check if rule is protected
        if rule.is_protected:
            logger.warning(f"Attempt to modify protected rule {rule_id} by user {current_user.id}")
            flash('This rule is protected and cannot be modified', 'warning')
            return redirect(url_for('rules.manage_rules'))
        
        # Check production environment restrictions
        if current_app.config.get('ENV') == 'production' and not current_app.config.get('ALLOW_PRODUCTION_RULES', False):
            logger.warning(f"Attempt to modify rule in protected production environment by user {current_user.id}")
            flash('Rule modifications are disabled in production environment', 'warning')
            return redirect(url_for('rules.manage_rules'))
        
        if request.method == 'POST':
            try:
                # Validate input
                pattern = request.form.get('pattern')
                description = request.form.get('description')
                category = request.form.get('category')
                is_regex = request.form.get('is_regex') == 'on'
                
                if not all([pattern, description, category]):
                    raise ValueError("All fields are required")
                
                # Validate regex pattern if applicable
                if is_regex:
                    try:
                        import re
                        re.compile(pattern)
                    except re.error as e:
                        raise ValueError(f"Invalid regular expression: {str(e)}")
                
                # Check if category is protected
                protected_categories = current_app.config.get('PROTECTED_CATEGORIES', [])
                if category in protected_categories and rule.category != category:
                    raise ValueError("Cannot assign to protected category")
                
                # Update rule with protection checks
                rule.pattern = pattern
                rule.description = description
                rule.category = category
                rule.is_regex = is_regex
                rule.updated_at = datetime.utcnow()
                
                db.session.commit()
                logger.info(f"Rule {rule_id} successfully updated by user {current_user.id}")
                flash('Rule updated successfully', 'success')
                
            except ValueError as ve:
                db.session.rollback()
                logger.error(f"Validation error updating rule {rule_id}: {str(ve)}")
                flash(str(ve), 'error')
                return render_template('rules/edit.html', rule=rule, 
                                    categories=current_app.config.get('RULE_CATEGORIES', []),
                                    protected_categories=current_app.config.get('PROTECTED_CATEGORIES', []),
                                    is_production=current_app.config.get('ENV') == 'production')
                
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error updating rule {rule_id}: {str(e)}")
                flash('An error occurred while updating the rule', 'error')
                return render_template('rules/edit.html', rule=rule,
                                    categories=current_app.config.get('RULE_CATEGORIES', []),
                                    protected_categories=current_app.config.get('PROTECTED_CATEGORIES', []),
                                    is_production=current_app.config.get('ENV') == 'production')
            
            return redirect(url_for('rules.manage_rules'))
        
        # GET request - display edit form
        return render_template('rules/edit.html', rule=rule,
                            categories=current_app.config.get('RULE_CATEGORIES', []),
                            protected_categories=current_app.config.get('PROTECTED_CATEGORIES', []),
                            is_production=current_app.config.get('ENV') == 'production')
        
    except Exception as e:
        logger.error(f"Unexpected error accessing rule {rule_id}: {str(e)}")
        flash('An unexpected error occurred', 'error')
        return redirect(url_for('rules.manage_rules'))

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
