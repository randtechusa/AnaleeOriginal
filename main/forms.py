
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import SelectField, SubmitField
from wtforms.validators import DataRequired
from flask_login import current_user
from models import Account

class UploadForm(FlaskForm):
    """Form for handling file uploads"""
    account = SelectField('Bank Account', 
                         validators=[DataRequired()],
                         description='Select the bank account for this statement')
    file = FileField('Statement File',
                    validators=[
                        FileRequired(),
                        FileAllowed(['csv', 'xlsx'], 'Only CSV and Excel files allowed')
                    ])
    submit = SubmitField('Upload')

    def __init__(self, *args, **kwargs):
        super(UploadForm, self).__init__(*args, **kwargs)
        if current_user.is_authenticated:
            accounts = Account.query.filter(
                Account.user_id == current_user.id,
                Account.link.ilike('ca.810%'),
                Account.is_active == True
            ).order_by(Account.link).all()
            
            self.account.choices = [(str(acc.id), f"{acc.link} - {acc.name}") 
                                  for acc in accounts]
