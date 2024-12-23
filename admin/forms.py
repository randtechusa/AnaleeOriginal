"""
Forms for admin functionality and company settings
Separated from main application forms to maintain isolation
"""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, TextAreaField, SelectField, SubmitField, IntegerField
from wtforms.validators import DataRequired, Length, Optional

class AdminChartOfAccountsForm(FlaskForm):
    """Form for managing system-wide Chart of Accounts"""
    account_code = StringField('Account Code', 
                           validators=[DataRequired(), Length(min=1, max=20)])
    name = StringField('Account Name', 
                    validators=[DataRequired(), Length(min=1, max=100)])
    category = SelectField('Category',
                       choices=[
                           ('Assets', 'Assets'),
                           ('Liabilities', 'Liabilities'),
                           ('Equity', 'Equity'),
                           ('Income', 'Income'),
                           ('Expenses', 'Expenses')
                       ],
                       validators=[DataRequired()])
    sub_category = StringField('Sub Category', 
                           validators=[Optional(), Length(max=50)])
    description = TextAreaField('Description', 
                            validators=[Optional(), Length(max=500)])
    account_type = SelectField('Account Type',
                           choices=[
                               ('Current Asset', 'Current Asset'),
                               ('Fixed Asset', 'Fixed Asset'),
                               ('Current Liability', 'Current Liability'),
                               ('Long Term Liability', 'Long Term Liability'),
                               ('Owner Equity', 'Owner Equity'),
                               ('Revenue', 'Revenue'),
                               ('Operating Expense', 'Operating Expense'),
                               ('Other Expense', 'Other Expense'),
                               ('Other', 'Other')
                           ],
                           validators=[Optional()])
    balance_sheet_category = SelectField('Balance Sheet Category',
                                     choices=[
                                         ('Asset', 'Asset'),
                                         ('Liability', 'Liability'),
                                         ('Equity', 'Equity'),
                                         ('Income Statement', 'Income Statement'),
                                         ('Off Balance Sheet', 'Off Balance Sheet')
                                     ],
                                     validators=[Optional()])
    status = SelectField('Status',
                      choices=[
                          ('Active', 'Active'),
                          ('Inactive', 'Inactive'),
                          ('Archived', 'Archived')
                      ],
                      default='Active',
                      validators=[Optional()])
    submit = SubmitField('Add Account')

class ChartOfAccountsUploadForm(FlaskForm):
    """Form for uploading Chart of Accounts Excel file"""
    excel_file = FileField('Excel File',
                        validators=[
                            FileRequired(),
                            FileAllowed(['xlsx'], 'Excel files only!')
                        ])
    submit = SubmitField('Upload Chart of Accounts')

class CompanySettingsForm(FlaskForm):
    """Form for company settings with CSRF protection"""
    company_name = StringField('Company Name', 
                           validators=[DataRequired(), Length(max=100)])
    registration_number = StringField('Registration Number', 
                                  validators=[Optional(), Length(max=50)])
    tax_number = StringField('Tax Number', 
                         validators=[Optional(), Length(max=50)])
    vat_number = StringField('VAT Number', 
                         validators=[Optional(), Length(max=50)])
    address = TextAreaField('Address', 
                        validators=[Optional(), Length(max=200)])
    financial_year_end = SelectField('Financial Year End',
                                 choices=[(str(i), str(i)) for i in range(1, 13)],
                                 validators=[DataRequired()])
    submit = SubmitField('Save Settings')