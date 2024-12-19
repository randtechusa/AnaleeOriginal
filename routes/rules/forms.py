import logging
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, IntegerField, BooleanField
from wtforms.validators import DataRequired, Length, Regexp, NumberRange, ValidationError
from flask import current_app
from models import Account, db

logger = logging.getLogger(__name__)

class RuleForm(FlaskForm):
    """Form for creating and editing rules with strict validation"""
    keyword = StringField('Keyword', validators=[
        DataRequired(),
        Length(min=2, max=200, message="Keyword must be between 2 and 200 characters"),
        Regexp(r'^[a-zA-Z0-9\s\|\-_\.]+$', message="Invalid characters in keyword")
    ])
    category = SelectField('Category', coerce=str, validators=[DataRequired()])
    priority = IntegerField('Priority', validators=[
        DataRequired(),
        NumberRange(min=1, max=100, message="Priority must be between 1 and 100")
    ])
    is_regex = BooleanField('Use Regular Expression', default=False)
    
    def __init__(self, *args, **kwargs):
        super(RuleForm, self).__init__(*args, **kwargs)
        self.protected_categories = set()
        self._load_categories()
    
    def _load_categories(self):
        """Load categories with proper protection"""
        try:
            # Get categories with environment protection
            query = db.session.query(Account.category).distinct()
            
            # Enhanced protection for production environment
            if current_app.config.get('ENV') == 'production':
                # Load protected categories
                protected_query = db.session.query(Account.category).filter(
                    Account.is_protected.is_(True)
                ).distinct()
                self.protected_categories = {category[0] for category in protected_query.all()}
                
                # Filter out protected categories
                query = query.filter(Account.is_protected.is_(False))
            
            # Load available categories
            categories = query.all()
            self.category.choices = [(c[0], c[0]) for c in categories]
            logger.info(f"Loaded {len(self.category.choices)} categories")
            
        except Exception as e:
            logger.error(f"Error loading categories in form: {str(e)}")
            self.category.choices = []
    
    def validate_category(self, field):
        """Additional validation for protected categories"""
        if field.data in self.protected_categories:
            raise ValidationError('Cannot create rules for protected categories')