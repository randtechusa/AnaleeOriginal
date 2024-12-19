import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import Transaction, Account, CompanySettings
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.sql import func

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import the blueprint instance from __init__.py
from . import reports

@reports.route('/cashbook')
@login_required
def cashbook():
    """Display bank statement cashbook report"""
    try:
        company_settings = CompanySettings.query.filter_by(user_id=current_user.id).first()
        if not company_settings:
            flash('Please configure company settings first.')
            return redirect(url_for('main.company_settings'))
            
        fy_dates = company_settings.get_financial_year()
        transactions = Transaction.query.filter(
            Transaction.user_id == current_user.id,
            Transaction.date.between(fy_dates['start_date'], fy_dates['end_date'])
        ).order_by(Transaction.date).all()
        
        return render_template('reports/cashbook.html',
                             transactions=transactions,
                             start_date=fy_dates['start_date'],
                             end_date=fy_dates['end_date'])
                             
    except Exception as e:
        logger.error(f"Error generating cashbook report: {str(e)}")
        flash('Error generating cashbook report')
        return redirect(url_for('main.dashboard'))

@reports.route('/general-ledger')
@login_required
def general_ledger():
    """Display general ledger report"""
    try:
        company_settings = CompanySettings.query.filter_by(user_id=current_user.id).first()
        if not company_settings:
            flash('Please configure company settings first.')
            return redirect(url_for('main.company_settings'))
            
        accounts = Account.query.filter_by(user_id=current_user.id).order_by(Account.link).all()
        
        return render_template('reports/general_ledger.html',
                             accounts=accounts)
                             
    except Exception as e:
        logger.error(f"Error generating general ledger: {str(e)}")
        flash('Error generating general ledger')
        return redirect(url_for('main.dashboard'))

@reports.route('/trial-balance')
@login_required
def trial_balance():
    """Display trial balance report"""
    try:
        company_settings = CompanySettings.query.filter_by(user_id=current_user.id).first()
        if not company_settings:
            flash('Please configure company settings first.')
            return redirect(url_for('main.company_settings'))
            
        fy_dates = company_settings.get_financial_year()
        accounts = Account.query.filter_by(user_id=current_user.id).order_by(Account.link).all()
        
        # Calculate totals for footer - corrected SQLAlchemy syntax
        total_debits = sum(account.balance for account in accounts if account.balance > 0)
        total_credits = sum(abs(account.balance) for account in accounts if account.balance < 0)
        
        return render_template('reports/trial_balance.html',
                             accounts=accounts,
                             start_date=fy_dates['start_date'],
                             end_date=fy_dates['end_date'],
                             total_debits=total_debits,
                             total_credits=total_credits)
                             
    except Exception as e:
        logger.error(f"Error generating trial balance: {str(e)}")
        flash('Error generating trial balance')
        return redirect(url_for('main.dashboard'))

@reports.route('/financial-position')
@login_required
def financial_position():
    """Display statement of financial position"""
    try:
        company_settings = CompanySettings.query.filter_by(user_id=current_user.id).first()
        if not company_settings:
            flash('Please configure company settings first.')
            return redirect(url_for('main.company_settings'))
            
        return render_template('reports/financial_position.html')
        
    except Exception as e:
        logger.error(f"Error generating financial position: {str(e)}")
        flash('Error generating financial position statement')
        return redirect(url_for('main.dashboard'))

@reports.route('/income-statement')
@login_required
def income_statement():
    """Display income statement"""
    try:
        company_settings = CompanySettings.query.filter_by(user_id=current_user.id).first()
        if not company_settings:
            flash('Please configure company settings first.')
            return redirect(url_for('main.company_settings'))
            
        return render_template('reports/income_statement.html')
        
    except Exception as e:
        logger.error(f"Error generating income statement: {str(e)}")
        flash('Error generating income statement')
        return redirect(url_for('main.dashboard'))