from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, IntegerField, BooleanField
from wtforms.validators import DataRequired, Length, Regexp, NumberRange
from flask import current_app
from models import Account, db

class RuleForm(FlaskForm):
    """Form for creating and editing rules with strict validation"""
    keyword = StringField('Keyword', validators=[
        DataRequired(),
        Length(min=2, max=200, message="Keyword must be between 2 and 200 characters"),
        Regexp(r'^[a-zA-Z0-9\s\|\-_\.]+$', message="Invalid characters in keyword")
    ])
    category = SelectField('Category', validators=[DataRequired()])
    priority = IntegerField('Priority', validators=[
        DataRequired(),
        NumberRange(min=1, max=100, message="Priority must be between 1 and 100")
    ])
    is_regex = BooleanField('Use Regular Expression')
    
    def __init__(self, *args, **kwargs):
        super(RuleForm, self).__init__(*args, **kwargs)
        
        # Dynamically load categories with protection
        try:
            # Get categories with environment protection
            query = db.session.query(Account.category).distinct()
            
            if current_app.config.get('ENV') == 'production':
                # In production, only show non-protected categories
                query = query.filter(Account.is_protected.is_(False))
                
            categories = query.all()
            self.category.choices = [(c[0], c[0]) for c in categories]
            
        except Exception as e:
            current_app.logger.error(f"Error loading categories in form: {str(e)}")
            self.category.choices = []
