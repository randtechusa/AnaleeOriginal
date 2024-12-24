"""
Forms specific to bank statement processing
Separates form handling from routes
"""
from flask_wtf import FlaskForm
from wtforms import FileField, SelectField, SubmitField
from wtforms.validators import DataRequired
from flask_login import current_user

from models import Account

class BankStatementUploadForm(FlaskForm):
    """Form for bank statement upload with CSRF protection"""
    account = SelectField(
        'Select Bank Account',
        validators=[DataRequired()],
        description='Select the bank account this statement belongs to'
    )
    file = FileField(
        'Bank Statement File',
        validators=[DataRequired()]
    )
    submit = SubmitField('Upload')

    def __init__(self, *args, **kwargs):
        """Initialize form and populate account choices"""
        super(BankStatementUploadForm, self).__init__(*args, **kwargs)
        if current_user.is_authenticated:
            try:
                # Get bank accounts (starting with ca.810)
                bank_accounts = Account.query.filter(
                    Account.user_id == current_user.id,
                    Account.link.like('ca.810%')
                ).all()
                self.account.choices = [
                    (str(acc.id), f"{acc.link} - {acc.name}")
                    for acc in bank_accounts
                ]
            except Exception as e:
                self.account.choices = []
