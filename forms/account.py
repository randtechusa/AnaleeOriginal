"""Form classes for account management"""
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField
from wtforms.validators import DataRequired, Length, Optional

class AccountForm(FlaskForm):
    """Form for managing user accounts with CSRF protection"""
    link = StringField('Link', validators=[DataRequired(), Length(min=1, max=100)])
    name = StringField('Account Name', validators=[DataRequired(), Length(min=1, max=100)])
    category = SelectField('Category', 
                         choices=[
                             ('Assets', 'Assets'),
                             ('Liabilities', 'Liabilities'),
                             ('Equity', 'Equity'),
                             ('Income', 'Income'),
                             ('Expenses', 'Expenses')
                         ],
                         validators=[DataRequired()])
    sub_category = StringField('Sub Category', validators=[Optional(), Length(max=50)])
    submit = SubmitField('Add Account')