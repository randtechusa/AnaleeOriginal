"""
Enhanced Predictive Features Module with comprehensive error handling and validation
"""
import logging
import os
from datetime import datetime
from difflib import SequenceMatcher
from typing import Dict, Any, List, Tuple, Optional

from models import Transaction

class PredictiveFeatures:
    def __init__(self):
        self.TEXT_SIMILARITY_THRESHOLD = 0.7
        self.MIN_DESCRIPTION_LENGTH = 3
        self.max_results = 5
        self.logger = logging.getLogger('predictive_features')
        self.setup_logging()
    
    def validate_input(self, description: str, explanation: str = "") -> Tuple[bool, str]:
        """Validate input parameters"""
        if not isinstance(description, str):
            return False, "Description must be a string"
        
        description = description.strip()
        if not description:
            return False, "Description cannot be empty"
            
        if len(description) < self.MIN_DESCRIPTION_LENGTH:
            return False, f"Description must be at least {self.MIN_DESCRIPTION_LENGTH} characters"
            
        return True, ""
    
    def setup_logging(self):
        """Configure logging for the predictive features module"""
        logger = logging.getLogger('predictive_features')
        if not logger.handlers:
            handler = logging.FileHandler('predictive_features.log')
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
    
    def find_similar_transactions(self, description: str, user_id: int = None) -> Dict[str, Any]:
        """Find similar transactions with comprehensive validation and error handling"""
        self.logger.info(f"ERF: Processing request for description: {description}")
        metrics = {'start_time': datetime.now(), 'processed': 0, 'errors': 0}
        
        try:
            # Enhanced input validation
            if not isinstance(description, str):
                return {'success': False, 'error': 'Description must be a string'}
            
            description = description.strip()
            if not description:
                return {'success': False, 'error': 'Description cannot be empty'}
            
            if len(description) < self.MIN_DESCRIPTION_LENGTH:
                return {'success': False, 'error': f'Description must be at least {self.MIN_DESCRIPTION_LENGTH} characters'}
            
            # Try to get current user if not provided
            if user_id is None:
                try:
                    from flask_login import current_user
                    if current_user and current_user.is_authenticated:
                        user_id = current_user.id
                except ImportError:
                    self.logger.warning("Failed to import current_user")
                except Exception as e:
                    self.logger.warning(f"Error getting current user: {str(e)}")
            
            # Build query with proper filtering
            query = Transaction.query.filter(
                Transaction.explanation.isnot(None),
                Transaction.description.isnot(None)
            )
            
            # Apply user filter if available 
            if user_id:
                query = query.filter(Transaction.user_id == user_id)
            
            # Get transactions
            transactions = query.all()
            self.logger.info(f"Found {len(transactions)} transactions to analyze")
            
            # Analyze similarity
            similar_transactions = []
            for transaction in transactions:
                try:
                    metrics['processed'] += 1
                    
                    # Skip transactions with same id if comparing with existing transaction
                    if hasattr(transaction, 'id') and getattr(transaction, 'id', None) == getattr(transaction, 'id', None):
                        continue
                        
                    # Calculate similarity using SequenceMatcher
                    text_similarity = SequenceMatcher(
                        None,
                        description.lower(),
                        transaction.description.lower()
                    ).ratio()
                    
                    # Additional check for sub-string matching
                    substring_match = False
                    if description.lower() in transaction.description.lower():
                        substring_match = True
                        # Boost similarity for substring matches
                        text_similarity = max(text_similarity, 0.75)
                    
                    # Analysis stats to include in results
                    analysis = {
                        'text_similarity': round(text_similarity, 2),
                        'substring_match': substring_match,
                        'confidence_avg': round(text_similarity, 2)
                    }
                    
                    if text_similarity >= self.TEXT_SIMILARITY_THRESHOLD:
                        similar_transactions.append({
                            'id': transaction.id,
                            'description': transaction.description,
                            'explanation': transaction.explanation,
                            'confidence': round(text_similarity, 2),
                            'match_type': 'text',
                            'account_id': transaction.account_id,
                            'account': transaction.account.name if transaction.account else None,
                            'date': transaction.date.strftime('%Y-%m-%d') if transaction.date else None,
                            'amount': float(transaction.amount) if transaction.amount else 0,
                            'analysis': analysis
                        })
                except Exception as tx_error:
                    metrics['errors'] += 1
                    self.logger.warning(f"Error processing transaction {transaction.id}: {str(tx_error)}")
                    continue
            
            # Sort by confidence and limit results
            similar_transactions.sort(key=lambda x: x['confidence'], reverse=True)
            similar_transactions = similar_transactions[:self.max_results]
            
            # Calculate metrics
            metrics['end_time'] = datetime.now()
            metrics['total_time'] = (metrics['end_time'] - metrics['start_time']).total_seconds()
            metrics['found'] = len(similar_transactions)
            
            # Return comprehensive results
            return {
                'success': True,
                'similar_transactions': similar_transactions,
                'metrics': metrics,
                'analysis': {
                    'confidence_avg': round(sum([t['confidence'] for t in similar_transactions]) / len(similar_transactions), 2) if similar_transactions else 0,
                    'top_match_confidence': similar_transactions[0]['confidence'] if similar_transactions else 0,
                    'similar_count': len(similar_transactions)
                }
            }
            
        except Exception as e:
            self.logger.error(f"ERF processing failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def suggest_account(self, description: str, explanation: str = "") -> List[Dict]:
        """Suggest accounts for a transaction based on description and explanation"""
        self.logger.info(f"ASF: Processing request for description: {description}")
        
        try:
            # Input validation
            valid, error_msg = self.validate_input(description, explanation)
            if not valid:
                self.logger.error(f"ASF validation error: {error_msg}")
                return []
            
            # Get user accounts
            from models import Account, Transaction
            from flask_login import current_user
            from flask import current_app

            # Get all accounts
            accounts = Account.query.filter_by(is_active=True).all()
            if not accounts:
                self.logger.warning("No accounts found for suggestions")
                return []
            
            suggestions = []
            description_lower = description.lower()
            explanation_lower = explanation.lower() if explanation else ""
            
            # Method 1: Exact keyword matching from account name or category
            for account in accounts:
                account_name = account.name.lower()
                account_type = account.type.lower() if account.type else ""
                
                # Check direct name matches
                if account_name in description_lower or account_name in explanation_lower:
                    suggestions.append({
                        'account': account.name,
                        'account_id': account.id,
                        'confidence': 0.95,
                        'reasoning': f"Direct match with account name: {account.name}",
                        'source': 'name_matching'
                    })
                    continue
                
                # Check account type matches
                if account_type and (account_type in description_lower or account_type in explanation_lower):
                    suggestions.append({
                        'account': account.name,
                        'account_id': account.id,
                        'confidence': 0.85,
                        'reasoning': f"Match with account type: {account.type}",
                        'source': 'type_matching'
                    })
                    continue
            
            # Method 2: Historical pattern matching from past transactions
            similar_transactions = Transaction.query.filter(
                Transaction.explanation.isnot(None),
                Transaction.account_id.isnot(None),
                Transaction.description.ilike(f"%{description}%")
            ).order_by(Transaction.date.desc()).limit(5).all()
            
            if similar_transactions:
                # Count occurrences of each account 
                account_counts = {}
                for tx in similar_transactions:
                    account_id = tx.account_id
                    if account_id not in account_counts:
                        account_counts[account_id] = 0
                    account_counts[account_id] += 1
                
                # Add suggestions based on historical patterns
                for account_id, count in account_counts.items():
                    account = Account.query.get(account_id)
                    if account:
                        confidence = min(0.90, 0.60 + (count / len(similar_transactions) * 0.30))
                        suggestions.append({
                            'account': account.name,
                            'account_id': account.id,
                            'confidence': round(confidence, 2),
                            'reasoning': f"Used {count} times for similar transactions",
                            'source': 'historical_pattern'
                        })
            
            # Method 3: Common accounting patterns
            common_patterns = {
                'expense': ['payment', 'purchase', 'bill', 'fee', 'expense', 'cost'],
                'income': ['deposit', 'salary', 'income', 'revenue', 'refund', 'sale'],
                'asset': ['acquisition', 'buy', 'invest', 'purchase', 'asset'],
                'liability': ['loan', 'debt', 'credit', 'financing', 'borrow']
            }
            
            for account in accounts:
                account_type = account.type.lower() if account.type else ""
                if account_type in common_patterns:
                    pattern_words = common_patterns[account_type]
                    matching_words = [word for word in pattern_words 
                                    if word in description_lower or word in explanation_lower]
                    
                    if matching_words:
                        confidence = 0.60 + (len(matching_words) / len(pattern_words) * 0.20)
                        suggestions.append({
                            'account': account.name,
                            'account_id': account.id,
                            'confidence': round(confidence, 2),
                            'reasoning': f"Contains {', '.join(matching_words)} which indicates {account_type}",
                            'source': 'pattern_matching'
                        })
            
            # Filter out low confidence suggestions
            suggestions = [s for s in suggestions if s['confidence'] >= 0.60]
            
            # Sort by confidence and remove duplicates
            suggestions.sort(key=lambda x: x['confidence'], reverse=True)
            
            # Keep only unique account suggestions (highest confidence for each account)
            unique_accounts = {}
            for suggestion in suggestions:
                account_id = suggestion['account_id']
                if account_id not in unique_accounts or unique_accounts[account_id]['confidence'] < suggestion['confidence']:
                    unique_accounts[account_id] = suggestion
            
            # Return top suggestions
            return list(unique_accounts.values())[:5]
            
        except Exception as e:
            self.logger.error(f"ASF processing failed: {str(e)}")
            return []
    
    def get_transaction_patterns(self, user_id: int) -> Dict[str, Any]:
        """Analyze transaction patterns for a user"""
        try:
            if not isinstance(user_id, int) or user_id <= 0:
                return {'success': False, 'error': 'Invalid user ID'}
                
            transactions = Transaction.query.filter_by(user_id=user_id).all()
            if not transactions:
                return {'success': False, 'error': 'No transactions found'}
                
            patterns = {
                'frequent_descriptions': {},
                'amount_ranges': {},
                'temporal_patterns': {}
            }
            
            for transaction in transactions:
                desc = transaction.description.lower() if transaction.description else 'unknown'
                patterns['frequent_descriptions'][desc] = patterns['frequent_descriptions'].get(desc, 0) + 1
                
                amount = float(transaction.amount) if transaction.amount else 0
                range_key = f"{int(amount/1000)}k-{int(amount/1000)+1}k"
                patterns['amount_ranges'][range_key] = patterns['amount_ranges'].get(range_key, 0) + 1
                
                if transaction.date:
                    month_key = transaction.date.strftime('%B')
                    patterns['temporal_patterns'][month_key] = patterns['temporal_patterns'].get(month_key, 0) + 1
            
            return {
                'success': True,
                'patterns': patterns,
                'total_analyzed': len(transactions)
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing transaction patterns: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'error_code': 'PATTERN_ANALYSIS_ERROR'
            }