import logging
from datetime import datetime
from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError
from models import db, KeywordRule, Account
from utils.rule_manager import RuleManager
from .forms import RuleForm

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Initialize rule manager
rule_manager = RuleManager()

@login_required
def manage_rules():
    """Display and manage keyword-based rules with environment protection"""
    try:
        # Get environment information
        is_production = current_app.config.get('ENV') == 'production'
        allow_production_rules = current_app.config.get('ALLOW_PRODUCTION_RULES', False)

        # Get rules with protection
        rules = rule_manager.get_active_rules(current_user.id)
        stats = rule_manager.get_rule_statistics()
        
        return render_template(
            'rules/manage.html',
            rules=rules,
            stats=stats,
            is_production=is_production,
            protected_categories=rule_manager.protected_categories
        )
    except Exception as e:
        logger.error(f"Error managing rules: {str(e)}")
        flash('Error loading rules', 'danger')
        return redirect(url_for('main.dashboard'))

@login_required
def create_rule():
    """Create a new rule with environment protection and enhanced validation"""
    try:
        # Environment protection check
        if current_app.config.get('ENV') == 'production' and not current_app.config.get('ALLOW_PRODUCTION_RULES', False):
            flash('Rule creation is disabled in production environment', 'warning')
            return redirect(url_for('rules.manage_rules'))
        
        # Initialize form with available categories
        form = RuleForm()
        
        # Get protected categories for template
        protected_categories = set()
        try:
            protected_accounts = Account.query.filter_by(is_protected=True).distinct(Account.category).all()
            protected_categories = {acc.category for acc in protected_accounts}
        except Exception as e:
            logger.error(f"Error loading protected categories: {str(e)}")
        
        if request.method == 'POST' and form.validate_on_submit():
            # Verify category protection
            if form.category.data in protected_categories:
                flash('Cannot create rules for protected categories', 'danger')
                return redirect(url_for('rules.create_rule'))
            
            # Create rule with protection
            keyword = form.keyword.data if form.keyword.data else ""
            category = form.category.data if form.category.data else ""
            priority = form.priority.data if form.priority.data is not None else 1
            
            success = rule_manager.add_rule(
                user_id=current_user.id,
                keyword=keyword.strip(),
                category=category.strip(),
                priority=priority,
                is_regex=form.is_regex.data or False
            )
            
            if success:
                flash('Rule created successfully', 'success')
                return redirect(url_for('rules.manage_rules'))
            else:
                flash('Error creating rule', 'danger')
        
        return render_template('rules/create.html', 
                             form=form,
                             protected_categories=protected_categories)
                             
    except Exception as e:
        logger.error(f"Error creating rule: {str(e)}")
        flash('Error creating rule', 'danger')
        return redirect(url_for('rules.manage_rules'))

@login_required
def toggle_rule(rule_id):
    """Toggle rule status with protection"""
    try:
        # Verify environment protection
        if current_app.config.get('ENV') == 'production' and not current_app.config.get('ALLOW_PRODUCTION_RULES', False):
            return jsonify({'error': 'Rule modification is disabled in production environment'}), 403

        rule = KeywordRule.query.get_or_404(rule_id)
        
        # Verify ownership and protection
        if rule.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized access'}), 403
            
        if rule.is_protected:
            return jsonify({'error': 'Cannot modify protected rule'}), 403

        # Toggle status
        rule.is_active = not rule.is_active
        rule.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({'success': True, 'is_active': rule.is_active})
    except Exception as e:
        logger.error(f"Error toggling rule: {str(e)}")
        return jsonify({'error': 'Failed to toggle rule status'}), 500

@login_required
def update_priority(rule_id):
    """Update rule priority with protection"""
    try:
        # Verify environment protection
        if current_app.config.get('ENV') == 'production' and not current_app.config.get('ALLOW_PRODUCTION_RULES', False):
            return jsonify({'error': 'Rule modification is disabled in production environment'}), 403

        data = request.get_json()
        new_priority = data.get('priority')

        if not isinstance(new_priority, int) or new_priority < 1 or new_priority > 100:
            return jsonify({'error': 'Invalid priority value'}), 400

        success = rule_manager.update_rule_priority(rule_id, new_priority)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Failed to update priority'}), 500
    except Exception as e:
        logger.error(f"Error updating priority: {str(e)}")
        return jsonify({'error': 'Failed to update priority'}), 500

# Routes are registered in __init__.py
