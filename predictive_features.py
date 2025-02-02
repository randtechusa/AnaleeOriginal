"""
Enhanced Predictive Features Module with improved explanation recognition
"""
import logging
from typing import Dict, List, Optional
from difflib import SequenceMatcher
import numpy as np
from sqlalchemy import text
from models import db, Transaction
from nlp_utils import get_openai_client, clean_text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PredictiveFeatures:
    def __init__(self):
        self.text_similarity_threshold = 0.70
        self.semantic_similarity_threshold = 0.80
        self._initialize_client()

    def _initialize_client(self):
        try:
            self.client = get_openai_client()
            logger.info("OpenAI client initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing OpenAI client: {str(e)}")
            self.client = None

    def find_similar_transactions(self, description: str, explanation: str = None) -> Dict:
        """Enhanced explanation recognition with hybrid matching system"""
        try:
            if not description and not explanation:
                return {'success': False, 'error': 'Description or explanation required', 'similar_transactions': []}

            logger.info(f"ERF: Finding similar transactions for '{description}'")
            
            # First try exact matches for efficiency
            exact_matches = Transaction.query.filter(
                Transaction.explanation.isnot(None),
                (Transaction.description.ilike(f"%{description}%")) |
                (Transaction.explanation.ilike(f"%{description}%") if explanation else False)
            ).all()

            if exact_matches:
                return {
                    'success': True, 
                    'similar_transactions': [{
                        'id': t.id,
                        'description': t.description,
                        'explanation': t.explanation,
                        'confidence': 1.0,
                        'match_type': 'exact'
                    } for t in exact_matches]
                }
                
            # Exact matches phase
            exact_matches = Transaction.query.filter(
                Transaction.explanation.isnot(None)
            ).filter(
                (Transaction.description == description) |
                (Transaction.explanation == explanation if explanation else False)
            ).all()

            if exact_matches:
                return {
                    'success': True,
                    'similar_transactions': [{
                        'id': t.id,
                        'description': t.description,
                        'explanation': t.explanation,
                        'confidence': 1.0,
                        'text_similarity': 1.0,
                        'semantic_similarity': 1.0,
                        'match_type': 'exact'
                    } for t in exact_matches]
                }
                
            # First try exact matches for efficiency
            exact_matches = Transaction.query.filter(
                Transaction.explanation.isnot(None)
            ).filter(
                (Transaction.description == description) |
                (Transaction.explanation == explanation if explanation else False)
            ).all()

            if exact_matches:
                return {
                    'success': True,
                    'similar_transactions': [{
                        'id': t.id,
                        'description': t.description,
                        'explanation': t.explanation,
                        'confidence': 1.0,
                        'match_type': 'exact'
                    } for t in exact_matches]
                }

            # Pattern matching phase
            pattern_matches = Transaction.query.filter(
                Transaction.explanation.isnot(None)
            ).filter(
                (Transaction.description.ilike(f"%{description}%")) |
                (Transaction.explanation.ilike(f"%{description}%"))
            ).all()

            matches = []
            for match in pattern_matches:
                # Enhanced text similarity with weighted token matching
                desc_words1 = set(description.lower().split())
                desc_words2 = set(match.description.lower().split())
                word_overlap = len(desc_words1.intersection(desc_words2)) / max(len(desc_words1), len(desc_words2))
                
                text_similarity = (
                    SequenceMatcher(None, description.lower(), match.description.lower()).ratio() * 0.6 +
                    word_overlap * 0.4
                )
                
                # Enhanced semantic similarity with contextual matching
                semantic_similarity = 0.0
                if explanation and match.explanation:
                    base_similarity = SequenceMatcher(
                        None,
                        explanation.lower(),
                        match.explanation.lower()
                    ).ratio()
                    
                    # Context matching
                    exp_words1 = set(explanation.lower().split())
                    exp_words2 = set(match.explanation.lower().split())
                    context_overlap = len(exp_words1.intersection(exp_words2)) / max(len(exp_words1), len(exp_words2))
                    
                    semantic_similarity = base_similarity * 0.7 + context_overlap * 0.3

                confidence = (text_similarity + semantic_similarity) / (2 if explanation else 1)
                
                if confidence >= self.text_similarity_threshold:
                    matches.append({
                        'id': match.id,
                        'description': match.description,
                        'explanation': match.explanation,
                        'confidence': confidence,
                        'text_similarity': text_similarity,
                        'semantic_similarity': semantic_similarity
                    })

            # First try exact matches
            exact_matches = Transaction.query.filter(
                (Transaction.description.ilike(f"%{description}%")) |
                (Transaction.explanation.isnot(None) & Transaction.explanation.ilike(f"%{description}%"))
            ).all()

            if exact_matches:
                return {
                    'success': True,
                    'similar_transactions': [{
                        'id': t.id,
                        'description': t.description,
                        'explanation': t.explanation,
                        'confidence': 1.0,
                        'match_type': 'exact'
                    } for t in exact_matches]
                }

            base_query = Transaction.query.filter(Transaction.explanation.isnot(None))
            if description:
                base_query = base_query.filter(Transaction.description.ilike(f"%{description}%"))

            transactions = base_query.all()
            similar_transactions = []

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

                confidence = (text_ratio + semantic_ratio) / 2
                if confidence >= self.text_similarity_threshold:
                    similar_transactions.append({
                        'id': transaction.id,
                        'description': transaction.description,
                        'explanation': transaction.explanation,
                        'confidence': confidence
                    })

            return {
                'success': True,
                'similar_transactions': sorted(
                    similar_transactions,
                    key=lambda x: x['confidence'],
                    reverse=True
                )[:5]
            }

        except Exception as e:
            logger.error(f"Error finding similar transactions: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'similar_transactions': []
            }

    def suggest_explanation(self, description: str, similar_transactions: List[Dict] = None) -> Dict:
        """Generate explanation suggestions with AI and pattern matching"""
        try:
            if not description:
                return {'success': False, 'error': 'Description required'}

            if not self.client:
                return self._pattern_match_explanation(description, similar_transactions)

            context = ""
            if similar_transactions:
                context = "\nSimilar transactions:\n" + "\n".join([
                    f"- {t['description']}: {t['explanation']}"
                    for t in similar_transactions[:3]
                ])

            prompt = f"""Analyze this transaction and suggest a clear explanation:
            Transaction: {clean_text(description)}
            {context}

            Provide a brief, professional explanation focusing on the business purpose."""

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a financial transaction analyst."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )

            explanation = response.choices[0].message.content.strip()
            return {
                'success': True,
                'explanation': explanation,
                'confidence': 0.9 if similar_transactions else 0.7
            }

        except Exception as e:
            logger.error(f"Error suggesting explanation: {str(e)}")
            return self._pattern_match_explanation(description, similar_transactions)

    def _pattern_match_explanation(self, description: str, similar_transactions: List[Dict] = None) -> Dict:
        """Fallback pattern matching for explanations"""
        try:
            if similar_transactions:
                best_match = max(similar_transactions, key=lambda x: x.get('confidence', 0))
                if best_match.get('confidence', 0) > 0.7:
                    return {
                        'success': True,
                        'explanation': best_match['explanation'],
                        'confidence': best_match['confidence']
                    }

            words = description.split()
            basic_explanation = f"Payment for {' '.join(words[:3])}..." if len(words) > 3 else description

            return {
                'success': True,
                'explanation': basic_explanation,
                'confidence': 0.3
            }

        except Exception as e:
            logger.error(f"Error in pattern matching: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }