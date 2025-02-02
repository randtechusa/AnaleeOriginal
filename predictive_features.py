
"""
Enhanced Predictive Features Module with advanced logging and error handling
"""
import logging
from typing import List, Dict, Optional
from difflib import SequenceMatcher
import numpy as np
from sqlalchemy import text
from models import db, Transaction, Account
from nlp_utils import get_openai_client, clean_text

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
fh = logging.FileHandler('predictive_features.log')
fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(fh)

class PredictiveFeatures:
    """Enhanced predictive features with advanced error handling"""

    def __init__(self):
        self.text_similarity_threshold = 0.70
        self.semantic_similarity_threshold = 0.95
        self._initialize_client()
        logger.info("PredictiveFeatures initialized with thresholds - Text: 70%, Semantic: 95%")

    def _initialize_client(self):
        """Initialize OpenAI client with error handling"""
        try:
            self.client = get_openai_client()
            if not self.client:
                logger.error("Failed to initialize OpenAI client")
            else:
                logger.info("OpenAI client initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing OpenAI client: {str(e)}")
            self.client = None

    def find_similar_transactions(self, description: str, explanation: str = None) -> Dict:
        """ERF: Enhanced transaction similarity detection with explanation recognition"""
        if not description and not explanation:
            logger.warning("Neither description nor explanation provided")
            return {'success': False, 'error': 'Description or explanation required', 'similar_transactions': []}

        try:
            # Query with explanation if provided
            base_query = Transaction.query.filter(Transaction.explanation.isnot(None))
            
            if description:
                base_query = base_query.filter(Transaction.description.ilike(f"%{description}%"))
            
            transactions = base_query.all()
            similar_transactions = []

            # Get current embedding if explanation provided
            current_embedding = None
            if self.client and explanation:
                try:
                    response = self.client.embeddings.create(
                        model="text-embedding-ada-002",
                        input=clean_text(explanation)
                    )
                    current_embedding = response.data[0].embedding
                except Exception as e:
                    logger.error(f"Error generating embedding: {str(e)}")

            for transaction in transactions:
                text_ratio = 0.0
                if description:
                    text_ratio = SequenceMatcher(
                        None, 
                        description.lower(), 
                        transaction.description.lower()
                    ).ratio()

                semantic_ratio = 1.0
                if current_embedding and transaction.explanation:
                    try:
                        response = self.client.embeddings.create(
                            model="text-embedding-ada-002",
                            input=clean_text(transaction.explanation)
                        )
                        tx_embedding = response.data[0].embedding
                        semantic_ratio = float(np.dot(current_embedding, tx_embedding))
                    except Exception as e:
                        logger.error(f"Error calculating semantic similarity: {str(e)}")

                # Adjust thresholds based on whether we're matching description, explanation, or both
                if ((description and text_ratio >= self.text_similarity_threshold) or 
                    (explanation and semantic_ratio >= self.semantic_similarity_threshold)):
                    similar_transactions.append({
                        'id': transaction.id,
                        'description': transaction.description,
                        'explanation': transaction.explanation,
                        'text_similarity': text_ratio,
                        'semantic_similarity': semantic_ratio
                    })

            return {
                'success': True,
                'similar_transactions': sorted(
                    similar_transactions,
                    key=lambda x: (x['semantic_similarity'], x['text_similarity']),
                    reverse=True
                )[:5]  # Return top 5 matches
            }
        try:
            logger.debug(f"Finding similar transactions for: {description}")
            
            if not description:
                logger.warning("Empty description provided")
                return {'success': False, 'error': 'Description required', 'similar_transactions': []}

            # Get transactions with explanations
            transactions = Transaction.query.filter(
                Transaction.explanation.isnot(None)
            ).all()
            
            logger.info(f"Found {len(transactions)} transactions with explanations")
            similar_transactions = []

            # Get current embedding if explanation provided
            current_embedding = None
            if self.client and explanation:
                try:
                    response = self.client.embeddings.create(
                        model="text-embedding-ada-002",
                        input=clean_text(explanation),
                        encoding_format="float"
                    )
                    current_embedding = response.data[0].embedding
                    logger.debug("Generated embedding for current explanation")
                except Exception as e:
                    logger.error(f"Error generating embedding: {str(e)}")

            for transaction in transactions:
                # Calculate similarities
                text_ratio = SequenceMatcher(
                    None, 
                    description.lower(), 
                    transaction.description.lower()
                ).ratio()
                
                semantic_ratio = 1.0
                if current_embedding and transaction.explanation:
                    try:
                        response = self.client.embeddings.create(
                            model="text-embedding-ada-002",
                            input=clean_text(transaction.explanation),
                            encoding_format="float"
                        )
                        tx_embedding = response.data[0].embedding
                        semantic_ratio = float(np.dot(current_embedding, tx_embedding))
                        logger.debug(f"Semantic similarity: {semantic_ratio:.3f}")
                    except Exception as e:
                        logger.error(f"Error calculating semantic similarity: {str(e)}")

                if (text_ratio >= self.text_similarity_threshold and 
                    semantic_ratio >= self.semantic_similarity_threshold):
                    similar_transactions.append({
                        'id': transaction.id,
                        'description': transaction.description,
                        'explanation': transaction.explanation,
                        'text_similarity': text_ratio,
                        'semantic_similarity': semantic_ratio
                    })

            logger.info(f"Found {len(similar_transactions)} similar transactions")
            return {
                'success': True,
                'similar_transactions': similar_transactions
            }

        except Exception as e:
            logger.error(f"Error in find_similar_transactions: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'similar_transactions': []
            }

    def suggest_account(self, description: str, explanation: str = None) -> Dict:
        """ASF: Enhanced account suggestion with context analysis"""
        try:
            logger.debug(f"Suggesting account for: {description}")
            
            if not description:
                return {
                    'success': False,
                    'error': 'Description required'
                }

            # Get active accounts
            accounts = Account.query.filter_by(is_active=True).all()
            if not accounts:
                logger.warning("No active accounts found")
                return {
                    'success': False,
                    'error': 'No active accounts available'
                }

            if not self.client:
                logger.error("OpenAI client unavailable")
                return self._fallback_account_suggestion(description, accounts)

            # Prepare account context
            account_context = "\n".join([
                f"- {acc.name} ({acc.category}): {acc.description if acc.description else 'No description'}"
                for acc in accounts
            ])

            prompt = f"""Analyze this transaction and suggest the most appropriate account:
            Transaction Description: {clean_text(description)}
            Additional Context: {clean_text(explanation) if explanation else 'No additional context'}

            Available Accounts:
            {account_context}

            Respond with:
            1. Most appropriate account name
            2. Confidence score (0-1)
            3. Reasoning
            Format: account|confidence|reasoning"""

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a financial account classification expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )

            result = response.choices[0].message.content.strip().split('|')
            
            if len(result) == 3:
                account_name, confidence, reasoning = result
                logger.info(f"Account suggestion generated: {account_name}")
                return {
                    'success': True,
                    'account': account_name.strip(),
                    'confidence': float(confidence.strip()),
                    'reasoning': reasoning.strip()
                }

        except Exception as e:
            logger.error(f"Error in suggest_account: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _fallback_account_suggestion(self, description: str, accounts: List[Account]) -> Dict:
        """Fallback account suggestion using basic text matching"""
        try:
            best_match = None
            highest_similarity = 0
            
            for account in accounts:
                similarity = SequenceMatcher(
                    None,
                    description.lower(),
                    f"{account.name} {account.category}".lower()
                ).ratio()
                
                if similarity > highest_similarity:
                    highest_similarity = similarity
                    best_match = account

            if best_match and highest_similarity > 0.3:
                return {
                    'success': True,
                    'account': best_match.name,
                    'confidence': highest_similarity,
                    'reasoning': 'Basic text similarity match'
                }
            
            return {
                'success': False,
                'error': 'No suitable account match found'
            }

        except Exception as e:
            logger.error(f"Error in fallback account suggestion: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def suggest_explanation(self, description: str) -> Dict:
        """ESF: Enhanced explanation suggestion with context analysis"""
        try:
            logger.debug(f"Generating explanation suggestion for: {description}")
            
            if not description:
                return {
                    'success': False,
                    'error': 'Description required'
                }

            if not self.client:
                logger.error("OpenAI client unavailable")
                return {
                    'success': False,
                    'error': 'AI service unavailable'
                }

            # Find similar transactions for context
            similar = self.find_similar_transactions(description)
            context = ""
            if similar['success'] and similar['similar_transactions']:
                context = "Similar transactions:\n" + "\n".join([
                    f"- Description: {t['description']}\n  Explanation: {t['explanation']}"
                    for t in similar['similar_transactions'][:3]
                ])

            prompt = f"""Generate a clear explanation for this financial transaction:
            Transaction: {clean_text(description)}
            
            {context}
            
            Provide:
            1. Clear, professional explanation
            2. Confidence score (0-1)
            Format: explanation|confidence"""

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a financial transaction analyst."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )

            result = response.choices[0].message.content.strip().split('|')
            
            if len(result) == 2:
                explanation, confidence = result
                logger.info("Explanation suggestion generated successfully")
                return {
                    'success': True,
                    'explanation': explanation.strip(),
                    'confidence': float(confidence.strip())
                }

        except Exception as e:
            logger.error(f"Error in suggest_explanation: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
