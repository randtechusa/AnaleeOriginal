"""
Reports module for financial reporting functionality
Handles generation and display of various financial reports including cashbook,
general ledger, and trial balance.
"""

import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Transaction, Account, CompanySettings
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
    """
    Display bank statement cashbook report with financial year and custom period filtering
    """
    try:
        company_settings = CompanySettings.query.filter_by(user_id=current_user.id).first()
        if not company_settings:
            flash('Please configure company settings first.')
            return redirect(url_for('main.company_settings'))

        # Get the earliest and latest transaction dates
        date_range = db.session.query(
            func.min(Transaction.date).label('min_date'),
            func.max(Transaction.date).label('max_date')
        ).filter(Transaction.user_id == current_user.id).first()

        # Set default dates if no transactions exist
        min_date = date_range.min_date or datetime.now()
        max_date = date_range.max_date or datetime.now()

        # Get available financial years based on data range
        financial_years = set()
        transactions = Transaction.query.filter_by(user_id=current_user.id).all()
        for t in transactions:
            if t.date.month > company_settings.financial_year_end:
                financial_years.add(t.date.year)
            else:
                financial_years.add(t.date.year - 1)
        financial_years = sorted(list(financial_years))

        # Determine filtering mode and dates
        period_type = request.args.get('period_type', 'fy')

        if period_type == 'custom':
            # Custom period filtering
            from_date = request.args.get('from_date')
            to_date = request.args.get('to_date')

            if from_date:
                from_date = datetime.strptime(from_date, '%Y-%m-%d').date()
            else:
                from_date = min_date

            if to_date:
                to_date = datetime.strptime(to_date, '%Y-%m-%d').date()
            else:
                to_date = max_date
        else:
            # Financial year filtering
            selected_fy = request.args.get('financial_year')
            if selected_fy:
                selected_fy = int(selected_fy)
            else:
                # Default to most recent financial year
                selected_fy = max(financial_years) if financial_years else datetime.now().year

            # Calculate FY dates based on settings
            if company_settings.financial_year_end == 12:
                from_date = datetime(selected_fy, 1, 1).date()
                to_date = datetime(selected_fy, 12, 31).date()
            else:
                from_date = datetime(selected_fy, company_settings.financial_year_end + 1, 1).date()
                to_date = datetime(selected_fy + 1, company_settings.financial_year_end, 
                                 company_settings.get_last_day_of_month(company_settings.financial_year_end)).date()

        # Get transactions for the specified period
        transactions = Transaction.query.filter(
            Transaction.user_id == current_user.id,
            Transaction.date.between(from_date, to_date)
        ).order_by(Transaction.date).all()

        return render_template('reports/cashbook.html',
                             transactions=transactions,
                             start_date=from_date,
                             end_date=to_date,
                             min_date=min_date,
                             max_date=max_date,
                             financial_years=financial_years,
                             current_fy=selected_fy if period_type == 'fy' else None)

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
        
        # Get accounts with their transactions
        accounts = (Account.query
                   .filter_by(user_id=current_user.id)
                   .outerjoin(Account.transactions)
                   .filter(
                       (Transaction.date >= fy_dates['start_date']) &
                       (Transaction.date <= fy_dates['end_date'])
                   )
                   .order_by(Account.link)
                   .all())
        
        # Calculate totals
        total_debits = 0
        total_credits = 0
        
        for account in accounts:
            balance = sum(t.amount for t in account.transactions)
            if balance > 0:
                total_debits += balance
            else:
                total_credits += abs(balance)
        
        return render_template('reports/trial_balance.html',
                             accounts=accounts,
                             start_date=fy_dates['start_date'],
                             end_date=fy_dates['end_date'],
                             total_debits=total_debits,
                             total_credits=total_credits)
                             
    except Exception as e:
        logger.error(f"Error generating trial balance: {str(e)}, Stack trace: {str(e.__traceback__)}")
        flash('Error loading transaction data. Please try again.')
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