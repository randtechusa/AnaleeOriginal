"""Admin routes for subscription management and system administration"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, abort, jsonify, session
from flask_login import login_required, current_user
from sqlalchemy import func
from datetime import datetime, timedelta
import logging
import pandas as pd

from models import db, User, AdminChartOfAccounts, Account, Transaction, CompanySettings, UploadedFile, BankStatementUpload, FinancialGoal, AlertConfiguration, AlertHistory
from .forms import AdminChartOfAccountsForm, ChartOfAccountsUploadForm, CompanySettingsForm
from admin import admin_required

# Create blueprint
bp = Blueprint('admin', __name__)
logger = logging.getLogger(__name__)

@bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Admin dashboard showing subscription and system statistics"""
    try:
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
    except Exception as e:
        logger.error(f"Error in admin dashboard: {str(e)}")
        flash('Error loading admin dashboard', 'error')
        return redirect(url_for('auth.login'))

@bp.route('/charts-of-accounts', methods=['GET'])
@login_required
@admin_required
def charts_of_accounts():
    """Manage system-wide Chart of Accounts"""
    form = AdminChartOfAccountsForm()
    upload_form = ChartOfAccountsUploadForm()

    # Changed to use the correct field name from the model
    accounts = AdminChartOfAccounts.query.order_by(AdminChartOfAccounts.code).all()

    # Get upload errors from session if they exist
    upload_errors = session.pop('upload_errors', None)

    return render_template('admin/charts_of_accounts.html', 
                         form=form, 
                         upload_form=upload_form,
                         accounts=accounts,
                         upload_errors=upload_errors)

@bp.route('/charts-of-accounts/upload', methods=['POST'])
@login_required
@admin_required
def upload_chart_of_accounts():
    """Upload Chart of Accounts from Excel file with enhanced error handling"""
    form = ChartOfAccountsUploadForm()
    if form.validate_on_submit():
        try:
            file = form.excel_file.data
            df = pd.read_excel(file)

            # Log the columns found in the Excel file
            current_app.logger.info(f"Excel columns found: {df.columns.tolist()}")

            # Create column mapping dictionary
            column_mapping = {
                'Code': ['Code', 'Account Code', 'AccountCode', 'Account_Code'],
                'Account Name': ['Account Name', 'AccountName', 'Name', 'Account_Name'],
                'Category': ['Category'],
                'Sub Category': ['Sub Category', 'SubCategory', 'Sub_Category'],
                'Description': ['Description', 'Desc'],
                'Links': ['Links', 'Link']
            }

            # Map Excel columns to expected names
            df_columns = {}
            for expected_col, possible_names in column_mapping.items():
                found = False
                for name in possible_names:
                    if name in df.columns:
                        df_columns[expected_col] = name
                        found = True
                        break
                if not found and expected_col in ['Code', 'Account Name', 'Category']:
                    flash(f'Required column {expected_col} not found in Excel file', 'danger')
                    return redirect(url_for('admin.charts_of_accounts'))

            success_count = 0
            error_count = 0
            skipped_count = 0
            error_details = []

            # Process each row with enhanced validation and error handling
            for idx, row in df.iterrows():
                try:
                    # Get values with proper null handling
                    code = str(row[df_columns['Code']]).strip()
                    link = str(row[df_columns['Links']]).strip() if 'Links' in df_columns else code

                    # Pre-validate required fields
                    if not code:
                        error_details.append({
                            'row': idx + 2,
                            'message': 'Code cannot be empty'
                        })
                        error_count += 1
                        continue

                    name = str(row[df_columns['Account Name']]).strip()
                    if not name:
                        error_details.append({
                            'row': idx + 2,
                            'message': 'Account Name cannot be empty'
                        })
                        error_count += 1
                        continue

                    category = str(row[df_columns['Category']]).strip()
                    if not category:
                        error_details.append({
                            'row': idx + 2,
                            'message': 'Category cannot be empty'
                        })
                        error_count += 1
                        continue

                    # Check for existing account by link or code
                    existing_account = AdminChartOfAccounts.query.filter(
                        (AdminChartOfAccounts.link == link) | 
                        (AdminChartOfAccounts.code == code)
                    ).first()

                    if existing_account:
                        error_details.append({
                            'row': idx + 2,
                            'message': f'Account with link {link} or code {code} already exists'
                        })
                        skipped_count += 1
                        continue

                    # Create new account with careful value assignment
                    account = AdminChartOfAccounts(
                        link=link,
                        code=code,
                        name=name,
                        category=category,
                        sub_category=str(row[df_columns.get('Sub Category', '')]).strip() if 'Sub Category' in df_columns else '',
                        description=str(row[df_columns.get('Description', '')]).strip() if 'Description' in df_columns else ''
                    )

                    db.session.add(account)
                    db.session.commit()  # Commit each record individually
                    success_count += 1

                except Exception as e:
                    db.session.rollback()
                    error_count += 1
                    error_details.append({
                        'row': idx + 2,
                        'message': str(e)
                    })
                    current_app.logger.error(f"Row {idx + 2}: {str(e)}")
                    continue

            if error_details:
                session['upload_errors'] = error_details
                flash('Upload completed with errors. See detailed error report below.', 'warning')
            else:
                session.pop('upload_errors', None)
                flash('Upload completed successfully.', 'success')

            flash(f'Uploaded {success_count} accounts successfully. {error_count} accounts failed. {skipped_count} accounts skipped (already exist).', 'info')

        except Exception as e:
            db.session.rollback()
            flash(f'Error uploading Chart of Accounts: {str(e)}', 'danger')
            current_app.logger.error(f"Error uploading COA: {str(e)}")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{getattr(form, field).label.text}: {error}', 'danger')

    return redirect(url_for('admin.charts_of_accounts'))

@bp.route('/charts-of-accounts/add', methods=['POST'])
@login_required
@admin_required
def add_chart_of_accounts():
    """Add a new account to system-wide Chart of Accounts"""
    form = AdminChartOfAccountsForm()
    if form.validate_on_submit():
        # Check if account code already exists
        existing_account = AdminChartOfAccounts.query.filter_by(
            code=form.account_code.data
        ).first()

        if existing_account:
            flash('Account code already exists.', 'error')
            return redirect(url_for('admin.charts_of_accounts'))

        account = AdminChartOfAccounts(
            code=form.account_code.data,
            name=form.name.data,
            category=form.category.data,
            sub_category=form.sub_category.data,
            description=form.description.data,
            link=form.account_code.data if not form.link.data else form.link.data
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

@bp.route('/charts-of-accounts/edit/<int:account_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_chart_of_accounts(account_id):
    """Edit an existing Chart of Accounts entry"""
    account = AdminChartOfAccounts.query.get_or_404(account_id)
    form = AdminChartOfAccountsForm(obj=account)

    if form.validate_on_submit():
        try:
            account.code = form.code.data
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

@bp.route('/charts-of-accounts/delete/<int:account_id>', methods=['POST'])
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


@bp.route('/active-subscribers')
@login_required
@admin_required
def active_subscribers():
    """View and manage active subscribers"""
    try:
        users = User.query.filter(
            User.is_admin == False,
            User.subscription_status == 'active'
        ).all()
        return render_template('admin/active_subscribers.html', users=users)
    except Exception as e:
        current_app.logger.error(f"Error loading active subscribers: {str(e)}")
        flash('Error loading active subscribers', 'error')
        return redirect(url_for('admin.dashboard'))

@bp.route('/deactivated-subscribers')
@login_required
@admin_required
def deactivated_subscribers():
    """View deactivated subscribers"""
    try:
        users = User.query.filter(
            User.is_admin == False,
            User.subscription_status == 'deactivated'
        ).all()
        return render_template('admin/deactivated_subscribers.html', users=users)
    except Exception as e:
        current_app.logger.error(f"Error loading deactivated subscribers: {str(e)}")
        flash('Error loading deactivated subscribers', 'error')
        return redirect(url_for('admin.dashboard'))

@bp.route('/pending-subscribers')
@login_required
@admin_required
def pending_subscribers():
    """View pending subscriber requests"""
    try:
        users = User.query.filter(
            User.is_admin == False,
            User.subscription_status == 'pending'
        ).all()
        return render_template('admin/pending_subscribers.html', users=users)
    except Exception as e:
        current_app.logger.error(f"Error loading pending subscribers: {str(e)}")
        flash('Error loading pending subscribers', 'error')
        return redirect(url_for('admin.dashboard'))

@bp.route('/subscriber/<int:user_id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_subscriber(user_id):
    """Approve a pending subscriber and set up their Chart of Accounts"""
    try:
        user = User.query.get_or_404(user_id)
        if user.is_admin:
            abort(400)  # Bad Request
        # First activate the subscription
        user.subscription_status = 'active'
        # Then create default accounts for the user
        User.create_default_accounts(user.id)
        db.session.commit()
        flash(f'Subscription activated for user {user.username} and Chart of Accounts created', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error activating subscription: {str(e)}")
        flash('Error activating subscription', 'error')
    return redirect(url_for('admin.pending_subscribers'))

@bp.route('/subscriber/<int:user_id>/deactivate', methods=['POST'])
@login_required
@admin_required
def deactivate_subscriber(user_id):
    """Deactivate a subscriber"""
    try:
        user = User.query.get_or_404(user_id)
        if user.is_admin:
            abort(400)  # Bad Request
        user.subscription_status = 'deactivated'
        db.session.commit()
        flash(f'Subscription deactivated for user {user.username}', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deactivating subscription: {str(e)}")
        flash('Error deactivating subscription', 'error')
    return redirect(url_for('admin.active_subscribers'))

@bp.route('/subscriber/<int:user_id>/suspend', methods=['POST'])
@login_required
@admin_required
def suspend_subscriber(user_id):
    """Temporarily suspend a subscriber's access"""
    try:
        user = User.query.get_or_404(user_id)
        if user.is_admin:
            abort(400)  # Bad Request
        user.suspend_subscription()
        db.session.commit()
        flash(f'Subscription suspended for user {user.username}', 'success')
        current_app.logger.info(f"Admin {current_user.username} suspended subscription for user {user.username}")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error suspending subscription: {str(e)}")
        flash('Error suspending subscription', 'error')
    return redirect(url_for('admin.active_subscribers'))

@bp.route('/subscriber/<int:user_id>/reactivate', methods=['POST'])
@login_required
@admin_required
def reactivate_subscriber(user_id):
    """Reactivate a suspended subscriber"""
    try:
        user = User.query.get_or_404(user_id)
        if user.is_admin:
            abort(400)  # Bad Request
        user.reactivate_subscription()
        db.session.commit()
        flash(f'Subscription reactivated for user {user.username}', 'success')
        current_app.logger.info(f"Admin {current_user.username} reactivated subscription for user {user.username}")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error reactivating subscription: {str(e)}")
        flash('Error reactivating subscription', 'error')
    return redirect(url_for('admin.deactivated_subscribers'))

@bp.route('/subscription-stats')
@login_required
@admin_required
def subscription_stats():
    """View detailed subscription statistics"""
    try:
        # Gather subscription statistics
        total_users = User.query.filter(User.is_admin == False).count()
        active_users = User.query.filter(
            User.is_admin == False,
            User.subscription_status == 'active'
        ).count()
        suspended_users = User.query.filter(
            User.is_admin == False,
            User.subscription_status == 'suspended'
        ).count()
        pending_users = User.query.filter(
            User.is_admin == False,
            User.subscription_status == 'pending'
        ).count()
        deactivated_users = User.query.filter(
            User.is_admin == False,
            User.subscription_status == 'deactivated'
        ).count()

        # Get recent subscription changes
        recent_changes = User.query.filter(
            User.is_admin == False,
            User.updated_at >= (datetime.utcnow() - timedelta(days=7))
        ).order_by(User.updated_at.desc()).limit(10).all()

        return render_template('admin/subscription_stats.html',
                           total_users=total_users,
                           active_users=active_users,
                           suspended_users=suspended_users,
                           pending_users=pending_users,
                           deactivated_users=deactivated_users,
                           recent_changes=recent_changes)
    except Exception as e:
        current_app.logger.error(f"Error loading subscription stats: {str(e)}")
        flash('Error loading subscription statistics', 'error')
        return redirect(url_for('admin.dashboard'))

@bp.route('/subscriber/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_subscriber(user_id):
    """Delete a deactivated subscriber and remove all associated data"""
    try:
        if current_app.config.get('MAINTENANCE_MODE', False):
            flash('System is in maintenance mode. Deletions are temporarily disabled.', 'warning')
            return redirect(url_for('admin.deactivated_subscribers'))

        user = User.query.get_or_404(user_id)

        if user.is_admin:
            abort(400)

        if user.subscription_status != 'deactivated':
            flash('Only deactivated users can be deleted', 'error')
            return redirect(url_for('admin.deactivated_subscribers'))

        current_app.logger.info(f"Admin {current_user.username} deleting user {user.username}")

        # Clear any active sessions for the user
        from flask import session
        session.clear()

        # Mark user as deleted
        user.soft_delete()
        
        # Delete related data using cascade
        db.session.delete(user)
        db.session.commit()

        flash(f'User {user.username} has been permanently deleted', 'success')
        current_app.logger.info(f"User {user.username} deleted successfully by admin {current_user.username}")

        # Logout if deleting self
        if current_user.id == user.id:
            from flask_login import logout_user
            logout_user()
            

    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        current_app.logger.error(f"Error deleting user {user.username if user else user_id}: {error_msg}")
        flash(f'Error deleting user: {error_msg}', 'error')

    return redirect(url_for('admin.deactivated_subscribers'))