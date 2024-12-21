import logging
from datetime import datetime
from flask import render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
import numpy as np
from sqlalchemy import func

from models import db, RiskAssessment, RiskIndicator, Transaction, Account
from . import risk_assessment
from .risk_analyzer import FinancialRiskAnalyzer

logger = logging.getLogger(__name__)

@risk_assessment.route('/dashboard')
@login_required
def dashboard():
    """Display risk assessment dashboard"""
    try:
        # Get latest risk assessment
        latest_assessment = RiskAssessment.query.filter_by(user_id=current_user.id)\
            .order_by(RiskAssessment.assessment_date.desc())\
            .first()
        
        # Get historical assessments for trending
        historical_assessments = RiskAssessment.query\
            .filter_by(user_id=current_user.id)\
            .order_by(RiskAssessment.assessment_date.desc())\
            .limit(10)\
            .all()
        
        return render_template(
            'risk_assessment/dashboard.html',
            latest_assessment=latest_assessment,
            historical_assessments=historical_assessments
        )
    except Exception as e:
        logger.error(f"Error in risk assessment dashboard: {str(e)}")
        flash('Error loading risk assessment dashboard', 'error')
        return redirect(url_for('main.dashboard'))

@risk_assessment.route('/analyze', methods=['POST'])
@login_required
def analyze():
    """Perform new risk assessment"""
    try:
        # Initialize risk analyzer
        analyzer = FinancialRiskAnalyzer()
        
        # Get recent transactions
        transactions = Transaction.query\
            .filter_by(user_id=current_user.id)\
            .order_by(Transaction.date.desc())\
            .limit(100)\
            .all()
        
        # Get account balances
        accounts = Account.query\
            .filter_by(user_id=current_user.id)\
            .all()
        
        # Perform risk assessment
        assessment_results = analyzer.assess_financial_risk(transactions, accounts)
        
        # Create new risk assessment record
        assessment = RiskAssessment(
            user_id=current_user.id,
            risk_score=assessment_results['risk_score'],
            risk_level=assessment_results['risk_level'],
            assessment_type='comprehensive',
            findings=assessment_results['findings'],
            recommendations=assessment_results['recommendations']
        )
        db.session.add(assessment)
        
        # Create risk indicators
        for indicator in assessment_results['indicators']:
            risk_indicator = RiskIndicator(
                assessment_id=assessment.id,
                indicator_name=indicator['name'],
                indicator_value=indicator['value'],
                threshold_value=indicator['threshold'],
                is_breach=indicator['is_breach']
            )
            db.session.add(risk_indicator)
        
        db.session.commit()
        flash('Risk assessment completed successfully', 'success')
        
        return redirect(url_for('risk_assessment.dashboard'))
        
    except Exception as e:
        logger.error(f"Error performing risk assessment: {str(e)}")
        db.session.rollback()
        flash('Error performing risk assessment', 'error')
        return redirect(url_for('risk_assessment.dashboard'))

@risk_assessment.route('/api/indicators')
@login_required
def get_indicators():
    """API endpoint for getting risk indicators"""
    try:
        latest_assessment = RiskAssessment.query\
            .filter_by(user_id=current_user.id)\
            .order_by(RiskAssessment.assessment_date.desc())\
            .first()
            
        if not latest_assessment:
            return jsonify({'error': 'No assessment found'}), 404
            
        indicators = [
            {
                'name': indicator.indicator_name,
                'value': indicator.indicator_value,
                'threshold': indicator.threshold_value,
                'is_breach': indicator.is_breach
            }
            for indicator in latest_assessment.indicators
        ]
        
        return jsonify(indicators)
        
    except Exception as e:
        logger.error(f"Error retrieving risk indicators: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
