"""
Admin routes for subscription management and system administration
Completely isolated from core application features
"""
from flask import render_template, redirect, url_for, flash, request, current_app, abort, send_file
from flask_login import current_user, login_required
from sqlalchemy import func
from datetime import datetime, timedelta
import pandas as pd
import os

from . import admin, admin_required
from models import db, User, AdminChartOfAccounts, Account
from .forms import AdminChartOfAccountsForm, ChartOfAccountsUploadForm

@admin.route('/charts-of-accounts/upload', methods=['POST'])
@login_required
@admin_required
def upload_chart_of_accounts():
    """Upload Chart of Accounts from Excel file"""
    form = ChartOfAccountsUploadForm()
    if form.validate_on_submit():
        try:
            file = form.excel_file.data
            df = pd.read_excel(file)

            # Log the columns found in the Excel file
            current_app.logger.info(f"Excel columns found: {df.columns.tolist()}")

            success_count = 0
            error_count = 0
            skipped_count = 0

            for _, row in df.iterrows():
                try:
                    # Check if account already exists
                    existing_account = AdminChartOfAccounts.query.filter_by(
                        account_code=str(row['Account Code'])
                    ).first()

                    if existing_account:
                        skipped_count += 1
                        continue

                    # Create new account with all available fields
                    account = AdminChartOfAccounts(
                        account_code=str(row['Account Code']),
                        name=str(row['Account Name']),
                        category=str(row['Category']),
                        sub_category=str(row['Sub Category']) if 'Sub Category' in row else '',
                        description=str(row['Description']) if 'Description' in row else '',
                        account_type=str(row['Account Type']) if 'Account Type' in row else '',
                        balance_sheet_category=str(row['Balance Sheet Category']) if 'Balance Sheet Category' in row else '',
                        status=str(row['Status']) if 'Status' in row else 'Active'
                    )
                    db.session.add(account)
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    current_app.logger.error(f"Error processing row: {str(e)}")
                    continue

            db.session.commit()
            flash(f'Uploaded {success_count} accounts successfully. {error_count} accounts failed. {skipped_count} accounts skipped (already exist).', 'success')

        except Exception as e:
            db.session.rollback()
            flash('Error uploading Chart of Accounts.', 'error')
            current_app.logger.error(f"Error uploading COA: {str(e)}")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{getattr(form, field).label.text}: {error}', 'error')

    return redirect(url_for('admin.charts_of_accounts'))

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

@admin.route('/charts-of-accounts', methods=['GET'])
@login_required
@admin_required
def charts_of_accounts():
    """Manage system-wide Chart of Accounts"""
    form = AdminChartOfAccountsForm()
    upload_form = ChartOfAccountsUploadForm()
    accounts = AdminChartOfAccounts.query.order_by(AdminChartOfAccounts.account_code).all()
    return render_template('admin/charts_of_accounts.html', 
                         form=form, 
                         upload_form=upload_form,
                         accounts=accounts)

@admin.route('/charts-of-accounts/add', methods=['POST'])
@login_required
@admin_required
def add_chart_of_accounts():
    """Add a new account to system-wide Chart of Accounts"""
    form = AdminChartOfAccountsForm()
    if form.validate_on_submit():
        # Check if account code already exists
        existing_account = AdminChartOfAccounts.query.filter_by(
            account_code=form.account_code.data
        ).first()

        if existing_account:
            flash('Account code already exists.', 'error')
            return redirect(url_for('admin.charts_of_accounts'))

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
        except Exception as e:
            db.session.rollback()
            flash('Error adding Chart of Accounts entry.', 'error')
            current_app.logger.error(f"Error adding admin COA: {str(e)}")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{getattr(form, field).label.text}: {error}', 'error')

    return redirect(url_for('admin.charts_of_accounts'))


@admin.route('/charts-of-accounts/edit/<int:account_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_chart_of_accounts(account_id):
    """Edit an existing Chart of Accounts entry"""
    account = AdminChartOfAccounts.query.get_or_404(account_id)
    form = AdminChartOfAccountsForm(obj=account)

    if form.validate_on_submit():
        try:
            account.account_code = form.account_code.data
            account.name = form.name.data
            account.category = form.category.data
            account.sub_category = form.sub_category.data
            account.description = form.description.data

            db.session.commit()
            flash('Account updated successfully.', 'success')
            return redirect(url_for('admin.charts_of_accounts'))
        except Exception as e:
            db.session.rollback()
            flash('Error updating account.', 'error')
            current_app.logger.error(f"Error updating admin COA: {str(e)}")

    return render_template('admin/edit_chart_of_accounts.html', form=form, account=account)

@admin.route('/charts-of-accounts/delete/<int:account_id>', methods=['POST'])
@login_required
@admin_required
def delete_chart_of_accounts(account_id):
    """Delete a Chart of Accounts entry"""
    account = AdminChartOfAccounts.query.get_or_404(account_id)

    try:
        db.session.delete(account)
        db.session.commit()
        flash('Account deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting account.', 'error')
        current_app.logger.error(f"Error deleting admin COA: {str(e)}")

    return redirect(url_for('admin.charts_of_accounts'))

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