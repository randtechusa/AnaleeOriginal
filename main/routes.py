"""Main routes for the application"""
import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Account, AdminChartOfAccounts

# Placeholder for PredictiveFeatures class - needs to be implemented separately
class PredictiveFeatures:
    def suggest_account(self, description, explanation):
        # Replace with actual prediction logic
        # This is a placeholder, replace with your actual implementation
        suggestions = [{'account': 'Asset', 'confidence': 0.8}, {'account': 'Liability', 'confidence': 0.2}]
        return suggestions

logger = logging.getLogger(__name__)
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

@main.route('/icountant', methods=['GET', 'POST'])
@login_required
def icountant():
    """iCountant Assistant route"""
    try:
        logger.debug("Accessing iCountant route")
        return render_template('icountant.html')
    except Exception as e:
        logger.error(f"Error in icountant route: {str(e)}", exc_info=True)
        flash('Error accessing iCountant Assistant', 'error')
        return redirect(url_for('main.dashboard'))

@main.route('/icountant_interface', methods=['GET', 'POST'])
@login_required
def icountant_interface():
    """Handle iCountant interface interactions"""
    try:
        return render_template('icountant.html')
    except Exception as e:
        logger.error(f"Error in iCountant interface: {str(e)}", exc_info=True)
        flash('Error processing request', 'error')
        return redirect(url_for('main.dashboard'))

@main.route('/upload', methods=['GET', 'POST'])
@login_required 
def upload():
    """Route for uploading data"""
    try:
        logger.debug("Accessing upload route")
        return render_template('upload.html')
    except Exception as e:
        logger.error(f"Error in upload route: {str(e)}", exc_info=True)
        flash('Error accessing upload page', 'error')
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

@main.route('/company_settings')
@login_required
def company_settings():
    """Company settings route"""
    try:
        logger.debug("Accessing company settings route")
        return render_template('company_settings.html')
    except Exception as e:
        logger.error(f"Error in company settings route: {str(e)}", exc_info=True)
        flash('Error accessing company settings', 'error')
        return redirect(url_for('main.dashboard'))

@main.route('/financial_insights')
@login_required
def financial_insights():
    """Financial insights dashboard route"""
    try:
        return render_template('financial_insights.html', financial_advice={})
    except Exception as e:
        logger.error(f"Error in financial insights route: {str(e)}", exc_info=True)
        flash('Error accessing Financial Insights', 'error')
        return redirect(url_for('main.dashboard'))

@main.route('/analyze/suggest-account', methods=['POST'])
@login_required
def suggest_account():
    """ASF: Get account suggestions with enhanced error handling"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        description = data.get('description', '').strip()
        explanation = data.get('explanation', '').strip()

        if not description:
            return jsonify({'success': False, 'error': 'Description required'}), 400

        predictor = PredictiveFeatures()
        suggestions = predictor.suggest_account(description, explanation)

        return jsonify(suggestions)

    except Exception as e:
        logger.error(f"Error in suggest_account route: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500