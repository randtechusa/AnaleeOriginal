"""
Admin routes for subscription management and system administration
Completely isolated from core application features
"""
from flask import render_template, redirect, url_for, flash, request, current_app, abort
from flask_login import current_user, login_required
from sqlalchemy import func
from datetime import datetime, timedelta

from . import admin, admin_required
from models import db, User, AdminChartOfAccounts, Account
from .forms import AdminChartOfAccountsForm

@admin.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Admin dashboard showing subscription and system statistics"""
    # Gather subscription statistics
    total_users = User.query.filter(User.is_admin == False).count()
    active_users = User.query.filter(
        User.is_admin == False,
        User.subscription_status == 'active'
    ).count()
    pending_users = User.query.filter(
        User.is_admin == False,
        User.subscription_status == 'pending'
    ).count()
    deactivated_users = User.query.filter(
        User.is_admin == False,
        User.subscription_status == 'deactivated'
    ).count()

    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         active_users=active_users,
                         pending_users=pending_users,
                         deactivated_users=deactivated_users)

@admin.route('/charts-of-accounts', methods=['GET', 'POST'])
@login_required
@admin_required
def charts_of_accounts():
    """Manage system-wide Chart of Accounts"""
    form = AdminChartOfAccountsForm()
    if form.validate_on_submit():
        account = AdminChartOfAccounts(
            account_code=form.account_code.data,
            name=form.name.data,
            category=form.category.data,
            sub_category=form.sub_category.data,
            description=form.description.data
        )
        try:
            db.session.add(account)
            db.session.commit()
            flash('Chart of Accounts entry added successfully.', 'success')
            return redirect(url_for('admin.charts_of_accounts'))
        except Exception as e:
            db.session.rollback()
            flash('Error adding Chart of Accounts entry.', 'error')
            current_app.logger.error(f"Error adding admin COA: {str(e)}")

    accounts = AdminChartOfAccounts.query.all()
    return render_template('admin/charts_of_accounts.html', form=form, accounts=accounts)

@admin.route('/active-subscribers')
@login_required
@admin_required
def active_subscribers():
    """View and manage active subscribers"""
    users = User.query.filter(
        User.is_admin == False,
        User.subscription_status == 'active'
    ).all()
    return render_template('admin/active_subscribers.html', users=users)

@admin.route('/deactivated-subscribers')
@login_required
@admin_required
def deactivated_subscribers():
    """View deactivated subscribers"""
    users = User.query.filter(
        User.is_admin == False,
        User.subscription_status == 'deactivated'
    ).all()
    return render_template('admin/deactivated_subscribers.html', users=users)

@admin.route('/subscriber/<int:user_id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_subscriber(user_id):
    """Approve a pending subscriber"""
    user = User.query.get_or_404(user_id)
    if user.is_admin:
        abort(400)  # Bad Request

    try:
        user.subscription_status = 'active'
        db.session.commit()
        flash(f'Subscription activated for user {user.username}', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error activating subscription: {str(e)}")
        flash('Error activating subscription', 'error')

    return redirect(url_for('admin.active_subscribers'))

@admin.route('/subscriber/<int:user_id>/deactivate', methods=['POST'])
@login_required
@admin_required
def deactivate_subscriber(user_id):
    """Deactivate a subscriber"""
    user = User.query.get_or_404(user_id)
    if user.is_admin:
        abort(400)  # Bad Request

    try:
        user.subscription_status = 'deactivated'
        db.session.commit()
        flash(f'Subscription deactivated for user {user.username}', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deactivating subscription: {str(e)}")
        flash('Error deactivating subscription', 'error')

    return redirect(url_for('admin.deactivated_subscribers'))