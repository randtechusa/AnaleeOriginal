from typing import List, Dict, Optional
import re
import os
import logging
from datetime import datetime
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError
from models import db, KeywordRule

logger = logging.getLogger(__name__)

class RuleManager:
    """Manages the storage and retrieval of keyword-based rules"""
    
    def __init__(self):
        self._cached_rules = None
        self._cache_timestamp = None
        self.cache_lifetime = 300  # 5 minutes cache lifetime
        self.is_production = os.environ.get('FLASK_ENV') == 'production'
        self.protect_data = True  # Always protect data in both environments
        
        # Enhanced protection for chart of accounts
        self.protected_categories = set()
        self._load_protected_categories()
        
    def _load_protected_categories(self):
        """Load protected categories from chart of accounts"""
        try:
            from models import Account
            protected_accounts = Account.query.filter_by(
                is_protected=True
            ).distinct(Account.category).all()
            
            self.protected_categories = {
                acc.category for acc in protected_accounts
            }
            logger.info(f"Loaded {len(self.protected_categories)} protected categories")
        except Exception as e:
            logger.error(f"Error loading protected categories: {str(e)}")
            # Fallback protection - protect all categories if loading fails
            self.protected_categories = set()
        
        # Configure strict logging for audit trail
        # Configure logger for audit trail
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
    def add_rule(self, user_id: int, keyword: str, category: str, priority: int = 1,
                 is_regex: bool = False, is_active: bool = True) -> bool:
        """
        Add a new keyword rule to the database with enhanced protection
        Returns True if successful, False otherwise
        """
        try:
            # Basic validation
            if not all([user_id, keyword, category]):
                self.logger.error("Missing required fields for rule creation")
                return False
            
            # Environment and data protection checks
            if self.is_production:
                if not current_app.config.get('ALLOW_PRODUCTION_RULES', False):
                    self.logger.warning(
                        "Rule creation blocked in production environment. "
                        "Use development environment for testing."
                    )
                    return False
                
                # Enhanced protection for production environment
                if self.protect_data:
                    # Verify category isn't protected
                    if category in self.protected_categories:
                        self.logger.warning(
                            f"Attempted to create rule for protected category: {category}"
                        )
                        return False
                    
                    # Verify user has access to this category
                    from models import Account
                    user_categories = {
                        acc.category for acc in Account.query.filter_by(
                            user_id=user_id,
                            is_active=True
                        ).all()
                    }
                    if category not in user_categories:
                        self.logger.warning(
                            f"User {user_id} attempted to create rule for unauthorized category: {category}"
                        )
                        return False
                
            # Validate input data
            if not all([user_id, keyword, category]):
                self.logger.error("Missing required fields for rule creation")
                return False
                
            # Validate regex pattern if applicable
            if is_regex:
                try:
                    re.compile(keyword)
                except re.error as e:
                    self.logger.error(f"Invalid regex pattern '{keyword}': {str(e)}")
                    return False
            
            # Create new rule
            rule = KeywordRule(
                user_id=user_id,
                keyword=keyword.lower().strip(),
                category=category.strip(),
                priority=priority,
                is_regex=is_regex,
                is_active=is_active,
                created_at=datetime.utcnow()
            )
            
            db.session.add(rule)
            db.session.commit()
            
            # Invalidate cache
            self._cached_rules = None
            return True
            
        except SQLAlchemyError as e:
            self.logger.error(f"Database error adding rule: {str(e)}")
            db.session.rollback()
            return False
            
    def get_active_rules(self, user_id: int) -> List[Dict]:
        """Get all active rules for a specific user with caching"""
        if not user_id:
            self.logger.error("User ID required for rule retrieval")
            return []
            
        # Check environment and data protection settings
        if self.protect_data:
            self.logger.info(f"Retrieving rules for user {user_id} with data protection enabled")
            
        # Use cache if available and valid
        if (self._cached_rules is not None and 
            self._cache_timestamp is not None and
            (datetime.utcnow() - self._cache_timestamp).total_seconds() < self.cache_lifetime):
            # Filter cached rules by user_id for security
            return [rule for rule in self._cached_rules if rule.get('user_id') == user_id]
            
        try:
            rules = KeywordRule.query.filter_by(user_id=user_id, is_active=True).order_by(
                KeywordRule.priority.desc()
            ).all()
            
            self._cached_rules = [
                {
                    'id': rule.id,
                    'keyword': rule.keyword,
                    'category': rule.category,
                    'priority': rule.priority,
                    'is_regex': rule.is_regex,
                    'created_at': rule.created_at
                }
                for rule in rules
            ]
            self._cache_timestamp = datetime.utcnow()
            
            return self._cached_rules
            
        except SQLAlchemyError as e:
            logger.error(f"Database error fetching rules: {str(e)}")
            return []
            
    def deactivate_rule(self, rule_id: int) -> bool:
        """
        Deactivate a rule instead of deleting it
        Returns True if successful, False otherwise
        """
        try:
            rule = KeywordRule.query.get(rule_id)
            if rule:
                rule.is_active = False
                db.session.commit()
                self._cached_rules = None
                return True
            return False
            
        except SQLAlchemyError as e:
            logger.error(f"Database error deactivating rule: {str(e)}")
            db.session.rollback()
            return False
            
    def update_rule_priority(self, rule_id: int, new_priority: int) -> bool:
        """
        Update the priority of a rule
        Returns True if successful, False otherwise
        """
        try:
            rule = KeywordRule.query.get(rule_id)
            if rule:
                rule.priority = new_priority
                db.session.commit()
                self._cached_rules = None
                return True
            return False
            
        except SQLAlchemyError as e:
            logger.error(f"Database error updating rule priority: {str(e)}")
            db.session.rollback()
            return False

    def get_rule_statistics(self) -> Dict:
        """Get statistics about the rules"""
        try:
            total_rules = KeywordRule.query.count()
            active_rules = KeywordRule.query.filter_by(is_active=True).count()
            regex_rules = KeywordRule.query.filter_by(is_regex=True).count()
            
            return {
                'total_rules': total_rules,
                'active_rules': active_rules,
                'regex_rules': regex_rules,
                'cached_rules': len(self._cached_rules) if self._cached_rules else 0,
                'cache_age': (datetime.utcnow() - self._cache_timestamp).total_seconds()
                if self._cache_timestamp else None
            }
            
        except SQLAlchemyError as e:
            logger.error(f"Database error getting rule statistics: {str(e)}")
            return {
                'total_rules': 0,
                'active_rules': 0,
                'regex_rules': 0,
                'cached_rules': 0,
                'cache_age': None
            }
