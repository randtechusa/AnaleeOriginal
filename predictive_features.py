<replit_final_file>
"""
Enhanced Predictive Features Module with improved explanation recognition
"""
import logging
from typing import Dict, List, Optional
from difflib import SequenceMatcher
import numpy as np
from sqlalchemy import text
from models import db, Transaction, Account

logger = logging.getLogger(__name__)

class PredictiveFeatures:
    def __init__(self):
        self.confidence_threshold = 0.7

    def find_similar_transactions(self, description: str) -> Dict:
        """Find similar transactions based on description"""
        try:
            similar_transactions = []
            # Get existing transactions with explanations
            transactions = Transaction.query.filter(
                Transaction.explanation.isnot(None)
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
                        'confidence': similarity
                    })

            return {
                'success': True,
                'similar_transactions': sorted(
                    similar_transactions,
                    key=lambda x: x['confidence'],
                    reverse=True
                )
            }
        except Exception as e:
            logger.error(f"Error finding similar transactions: {str(e)}")
            return {'success': False, 'error': str(e)}

    def suggest_account(self, description: str, explanation: str = "") -> List[Dict]:
        """Suggest accounts based on transaction details"""
        try:
            suggestions = []
            accounts = Account.query.filter_by(is_active=True).all()

            for account in accounts:
                # Match against account name and category
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

                # Weight the similarities
                confidence = (name_similarity * 0.7) + (category_similarity * 0.3)

                if confidence >= self.confidence_threshold:
                    suggestions.append({
                        'account': {
                            'id': account.id,
                            'name': account.name,
                            'category': account.category
                        },
                        'confidence': confidence,
                        'reasoning': f"Matched based on account name ({name_similarity:.0%}) and category ({category_similarity:.0%})"
                    })

            return sorted(suggestions, key=lambda x: x['confidence'], reverse=True)

        except Exception as e:
            logger.error(f"Error suggesting account: {str(e)}")
            return []