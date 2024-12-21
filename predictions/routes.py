"""
Routes for AI-powered financial predictions
Keeps prediction functionality separate from core features
"""

from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
import logging

from predictive_analysis import FinancialTrendAnalyzer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create blueprint
predictions = Blueprint('predictions', __name__)

@predictions.route('/financial-trends')
@login_required
def financial_trends():
    """Display financial trends and predictions"""
    try:
        analyzer = FinancialTrendAnalyzer()
        months_back = request.args.get('months', type=int, default=12)
        
        # Get trend analysis
        analysis = analyzer.analyze_trends(current_user.id, months_back)
        
        if analysis['status'] == 'error':
            logger.error(f"Error in trend analysis: {analysis['message']}")
            return render_template(
                'predictions/trends.html',
                error=analysis['message']
            )
            
        return render_template(
            'predictions/trends.html',
            analysis=analysis
        )
        
    except Exception as e:
        logger.error(f"Error displaying financial trends: {str(e)}")
        return render_template(
            'predictions/trends.html',
            error="Error generating financial trends"
        )

@predictions.route('/api/predictions')
@login_required
def get_predictions():
    """API endpoint for getting updated predictions"""
    try:
        analyzer = FinancialTrendAnalyzer()
        months_back = request.args.get('months', type=int, default=12)
        
        analysis = analyzer.analyze_trends(current_user.id, months_back)
        return jsonify(analysis)
        
    except Exception as e:
        logger.error(f"Error getting predictions: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
