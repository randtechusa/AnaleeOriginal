from flask import jsonify, request
from flask_login import login_required, current_user
from models import Transaction
from . import suggestions

@suggestions.route('/explanation', methods=['POST'])
@login_required
def suggest_explanation_api():
    """API endpoint for explanation suggestions"""
    try:
        data = request.get_json()
        description = data.get('description', '').strip()

        if not description:
            return jsonify({'error': 'Description is required'}), 400

        # Find similar transactions based on description
        similar_transactions = Transaction.query.filter(
            Transaction.user_id == current_user.id,
            Transaction.description.ilike(f"%{description}%")
        ).limit(5).all()

        # Convert to JSON-serializable format
        transactions = [{
            'id': t.id,
            'description': t.description,
            'explanation': t.explanation
        } for t in similar_transactions]

        return jsonify({
            'success': True,
            'transactions': transactions
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500
