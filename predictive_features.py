"""
Predictive Features Module for Analyze Data Menu
Implements the three key predictive features:
1. Explanation Recognition Feature (ERF)
2. Account Suggestion Feature (ASF)
3. Explanation Suggestion Feature (ESF)
"""

import logging
from typing import List, Dict, Tuple, Optional
from difflib import SequenceMatcher
import numpy as np
from sqlalchemy import text
from models import db, Transaction, Account
from nlp_utils import get_openai_client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PredictiveFeatures:
    """Handles all predictive features for transaction analysis"""
    
    def __init__(self):
        self.text_similarity_threshold = 0.70  # 70% text similarity
        self.semantic_similarity_threshold = 0.95  # 95% semantic similarity
        self.client = get_openai_client()
        
    def find_similar_transactions(self, description: str, explanation: str) -> List[Dict]:
        """
        ERF: Find similar transactions based on text and semantic similarity
        
        Args:
            description: Current transaction description
            explanation: Current transaction explanation
            
        Returns:
            List of similar transactions with their similarity scores
        """
        try:
            # Get all transactions with explanations
            transactions = Transaction.query.filter(
                Transaction.explanation.isnot(None)
            ).all()
            
            similar_transactions = []
            for transaction in transactions:
                # Calculate text similarity
                text_ratio = SequenceMatcher(
                    None, 
                    description.lower(), 
                    transaction.description.lower()
                ).ratio()
                
                if text_ratio >= self.text_similarity_threshold:
                    similar_transactions.append({
                        'id': transaction.id,
                        'description': transaction.description,
                        'explanation': transaction.explanation,
                        'text_similarity': text_ratio,
                        'semantic_similarity': 1.0  # Default until semantic analysis is implemented
                    })
            
            return similar_transactions
            
        except Exception as e:
            logger.error(f"Error finding similar transactions: {str(e)}")
            return []
            
    def suggest_account(self, description: str, explanation: str) -> Dict:
        """
        ASF: Suggest account based on description and explanation
        
        Args:
            description: Transaction description
            explanation: Transaction explanation
            
        Returns:
            Dictionary containing suggested account and confidence score
        """
        try:
            # Get active accounts
            accounts = Account.query.filter_by(is_active=True).all()
            
            if not accounts:
                return {
                    'success': False,
                    'message': 'No active accounts found'
                }
                
            # Combine description and explanation for analysis
            combined_text = f"{description} - {explanation}"
            
            # Get AI suggestion if client available
            if self.client:
                try:
                    response = self.client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": "You are a financial account categorization expert."},
                            {"role": "user", "content": f"Suggest the most appropriate account for this transaction:\n{combined_text}\n\nAvailable accounts:\n{[acc.name for acc in accounts]}"}
                        ],
                        temperature=0.3
                    )
                    
                    suggestion = response.choices[0].message.content
                    
                    # Parse suggestion to match with available accounts
                    best_match = None
                    highest_similarity = 0
                    
                    for account in accounts:
                        similarity = SequenceMatcher(
                            None,
                            account.name.lower(),
                            suggestion.lower()
                        ).ratio()
                        
                        if similarity > highest_similarity:
                            highest_similarity = similarity
                            best_match = account
                            
                    return {
                        'success': True,
                        'account': best_match.name if best_match else None,
                        'confidence': highest_similarity,
                        'reasoning': suggestion
                    }
                    
                except Exception as e:
                    logger.error(f"Error getting AI suggestion: {str(e)}")
                    
            # Fallback to basic matching
            return self._basic_account_matching(combined_text, accounts)
            
        except Exception as e:
            logger.error(f"Error suggesting account: {str(e)}")
            return {
                'success': False,
                'message': f'Error suggesting account: {str(e)}'
            }
            
    def suggest_explanation(self, description: str) -> Dict:
        """
        ESF: Suggest explanation based on transaction description and past data
        
        Args:
            description: Transaction description
            
        Returns:
            Dictionary containing suggested explanation and confidence score
        """
        try:
            # Find similar past transactions
            similar_transactions = self.find_similar_transactions(description, '')
            
            if similar_transactions:
                # Use the explanation from the most similar transaction
                best_match = max(
                    similar_transactions,
                    key=lambda x: x['text_similarity']
                )
                
                return {
                    'success': True,
                    'explanation': best_match['explanation'],
                    'confidence': best_match['text_similarity'],
                    'source': 'historical_data'
                }
                
            # If no similar transactions found and AI available, get AI suggestion
            if self.client:
                try:
                    response = self.client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": "You are a financial transaction expert."},
                            {"role": "user", "content": f"Suggest a clear explanation for this transaction:\n{description}"}
                        ],
                        temperature=0.3
                    )
                    
                    return {
                        'success': True,
                        'explanation': response.choices[0].message.content,
                        'confidence': 0.7,  # Default confidence for AI suggestions
                        'source': 'ai_generated'
                    }
                    
                except Exception as e:
                    logger.error(f"Error getting AI explanation: {str(e)}")
            
            return {
                'success': False,
                'message': 'No similar transactions found and AI unavailable'
            }
            
        except Exception as e:
            logger.error(f"Error suggesting explanation: {str(e)}")
            return {
                'success': False,
                'message': f'Error suggesting explanation: {str(e)}'
            }
            
    def _basic_account_matching(self, text: str, accounts: List[Account]) -> Dict:
        """Basic account matching when AI is unavailable"""
        try:
            best_match = None
            highest_similarity = 0
            
            for account in accounts:
                # Compare with account name and category
                name_similarity = SequenceMatcher(
                    None,
                    text.lower(),
                    f"{account.name} {account.category}".lower()
                ).ratio()
                
                if name_similarity > highest_similarity:
                    highest_similarity = name_similarity
                    best_match = account
                    
            return {
                'success': True,
                'account': best_match.name if best_match else None,
                'confidence': highest_similarity,
                'reasoning': 'Based on text similarity with account name and category'
            }
            
        except Exception as e:
            logger.error(f"Error in basic account matching: {str(e)}")
            return {
                'success': False,
                'message': f'Error in basic account matching: {str(e)}'
            }
