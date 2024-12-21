import logging
from datetime import datetime
from flask import render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func

from models import db, Transaction, Account, FinancialRecommendation, RecommendationMetrics
from . import recommendations
from .ai_recommender import FinancialRecommender

logger = logging.getLogger(__name__)

@recommendations.route('/dashboard')
@login_required
def dashboard():
    """Display AI-driven financial recommendations dashboard"""
    try:
        # Get active recommendations
        active_recommendations = FinancialRecommendation.query\
            .filter_by(user_id=current_user.id)\
            .filter(FinancialRecommendation.status.in_(['new', 'in_progress']))\
            .order_by(FinancialRecommendation.priority.desc())\
            .all()
        
        # Get completed recommendations
        completed_recommendations = FinancialRecommendation.query\
            .filter_by(user_id=current_user.id, status='completed')\
            .order_by(FinancialRecommendation.applied_at.desc())\
            .limit(5)\
            .all()
        
        return render_template(
            'recommendations/dashboard.html',
            active_recommendations=active_recommendations,
            completed_recommendations=completed_recommendations
        )
    except Exception as e:
        logger.error(f"Error in recommendations dashboard: {str(e)}")
        flash('Error loading recommendations dashboard', 'error')
        return redirect(url_for('main.dashboard'))

@recommendations.route('/generate', methods=['POST'])
@login_required
def generate():
    """Generate new AI-driven recommendations"""
    try:
        # Get recent transactions and accounts
        transactions = Transaction.query\
            .filter_by(user_id=current_user.id)\
            .order_by(Transaction.date.desc())\
            .limit(100)\
            .all()
            
        accounts = Account.query\
            .filter_by(user_id=current_user.id)\
            .all()
        
        # Initialize recommender and generate recommendations
        recommender = FinancialRecommender()
        new_recommendations = recommender.generate_recommendations(transactions, accounts)
        
        # Save recommendations
        for rec in new_recommendations:
            if rec:
                recommendation = FinancialRecommendation(
                    user_id=current_user.id,
                    category=rec['category'],
                    priority=rec['priority'],
                    recommendation=rec['recommendation'],
                    impact_score=rec['impact_score']
                )
                db.session.add(recommendation)
        
        db.session.commit()
        flash('New recommendations generated successfully', 'success')
        
        return redirect(url_for('recommendations.dashboard'))
        
    except Exception as e:
        logger.error(f"Error generating recommendations: {str(e)}")
        db.session.rollback()
        flash('Error generating recommendations', 'error')
        return redirect(url_for('recommendations.dashboard'))

@recommendations.route('/update/<int:id>', methods=['POST'])
@login_required
def update_status():
    """Update recommendation status"""
    try:
        recommendation = FinancialRecommendation.query\
            .filter_by(id=id, user_id=current_user.id)\
            .first_or_404()
            
        new_status = request.form.get('status')
        if new_status in ['in_progress', 'completed', 'dismissed']:
            recommendation.status = new_status
            if new_status == 'completed':
                recommendation.applied_at = datetime.utcnow()
            db.session.commit()
            flash('Recommendation status updated', 'success')
        else:
            flash('Invalid status', 'error')
            
        return redirect(url_for('recommendations.dashboard'))
        
    except Exception as e:
        logger.error(f"Error updating recommendation: {str(e)}")
        db.session.rollback()
        flash('Error updating recommendation', 'error')
        return redirect(url_for('recommendations.dashboard'))
