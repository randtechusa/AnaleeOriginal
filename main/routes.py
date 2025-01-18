"""Main routes for the application"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Account, AdminChartOfAccounts

main = Blueprint('main', __name__)

@main.route('/')
@main.route('/index')
@login_required
def index():
    return render_template('index.html')

@main.route('/analyze_list')
@login_required
def analyze_list():
    """Route for analyze data menu - protected core functionality"""
    return render_template('analyze_list.html')

@main.route('/dashboard')
@login_required 
def dashboard():
    """Main dashboard route"""
    return render_template('dashboard.html')

@main.route('/icountant')
@login_required
def icountant():
    """iCountant Assistant route"""
    try:
        return render_template('icountant.html')
    except Exception as e:
        logger.error(f"Error in icountant route: {str(e)}", exc_info=True)
        flash('Error accessing iCountant Assistant', 'error')
        return redirect(url_for('main.dashboard'))

@main.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Protected Chart of Accounts management"""
    try:
        if request.method == 'POST':
            account = Account(
                link=request.form['link'],
                name=request.form['name'],
                category=request.form['category'],
                sub_category=request.form.get('sub_category', ''),
                account_code=request.form.get('account_code', ''),
                user_id=current_user.id
            )
            db.session.add(account)
            db.session.commit()
            flash('Account added successfully', 'success')

        # Get user's accounts
        accounts = Account.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).all()

        # Get system-wide Chart of Accounts for reference
        system_accounts = AdminChartOfAccounts.query.all()

        return render_template(
            'settings.html',
            accounts=accounts,
            system_accounts=system_accounts
        )
    except Exception as e:
        db.session.rollback()
        flash('Error accessing Chart of Accounts', 'error')
        return redirect(url_for('main.dashboard'))

@main.route('/admin_dashboard')
@login_required
def admin_dashboard():
    return render_template('admin/dashboard.html')