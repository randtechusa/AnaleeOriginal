
"""
Enhanced Predictive Features Module with improved validation and error handling
"""
import logging
from typing import Dict, List, Optional, Any
from difflib import SequenceMatcher
import numpy as np
from sqlalchemy import text
from models import db, Transaction, Account

logger = logging.getLogger(__name__)

class PredictiveFeatures:
    def __init__(self):
        self.confidence_threshold = 0.7
        self.min_description_length = 3

    def find_similar_transactions(self, description: str) -> Dict[str, Any]:
        """Find similar transactions based on description with enhanced validation"""
        try:
            if not description or len(description.strip()) < self.min_description_length:
                return {
                    'success': False,
                    'error': 'Description too short or empty'
                }

            similar_transactions = []
            transactions = Transaction.query.filter(
                Transaction.explanation.isnot(None),
                Transaction.description.isnot(None)
            ).all()

            for transaction in transactions:
                similarity = SequenceMatcher(
                    None,
                    description.lower(),
                    transaction.description.lower()
                ).ratio()

                if similarity >= self.confidence_threshold:
                    similar_transactions.append({
                        'id': transaction.id,
                        'description': transaction.description,
                        'explanation': transaction.explanation,
                        'confidence': round(similarity, 2),
                        'account_id': transaction.account_id
                    })

            return {
                'success': True,
                'similar_transactions': sorted(
                    similar_transactions,
                    key=lambda x: x['confidence'],
                    reverse=True
                )[:5]  # Limit to top 5 matches
            }
        except Exception as e:
            logger.error(f"Error finding similar transactions: {str(e)}")
            return {'success': False, 'error': str(e)}

    def suggest_account(self, description: str, explanation: str = "") -> List[Dict]:
        """Suggest accounts based on transaction details with enhanced matching"""
        try:
            if not description or len(description.strip()) < self.min_description_length:
                return []

            suggestions = []
            accounts = Account.query.filter_by(is_active=True).all()

            # Get historical matches
            historical_matches = Transaction.query.filter(
                Transaction.description.ilike(f"%{description}%"),
                Transaction.account_id.isnot(None)
            ).distinct(Transaction.account_id).all()

            # Add historical matches first
            for match in historical_matches:
                if match.account:
                    suggestions.append({
                        'account': {
                            'id': match.account.id,
                            'name': match.account.name,
                            'category': match.account.category
                        },
                        'confidence': 0.9,
                        'reasoning': 'Based on historical transaction patterns'
                    })

            # Add pattern-based matches
            for account in accounts:
                name_similarity = SequenceMatcher(
                    None,
                    description.lower(),
                    account.name.lower()
                ).ratio()

                category_similarity = SequenceMatcher(
                    None,
                    description.lower(),
                    account.category.lower()
                ).ratio()

                confidence = (name_similarity * 0.7) + (category_similarity * 0.3)

                if confidence >= self.confidence_threshold:
                    suggestion = {
                        'account': {
                            'id': account.id,
                            'name': account.name,
                            'category': account.category
                        },
                        'confidence': round(confidence, 2),
                        'reasoning': f"Pattern match: name ({name_similarity:.0%}), category ({category_similarity:.0%})"
                    }
                    
                    if suggestion not in suggestions:
                        suggestions.append(suggestion)

            return sorted(suggestions, key=lambda x: x['confidence'], reverse=True)[:5]

        except Exception as e:
            logger.error(f"Error suggesting account: {str(e)}")
            return []
