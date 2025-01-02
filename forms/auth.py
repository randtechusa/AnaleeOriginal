"""
Authentication related forms including login, password reset and MFA
"""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
from models import User, db

class LoginForm(FlaskForm):
    """Form for user login with CSRF protection"""
    email = StringField('Email', validators=[
        DataRequired(),
        Email(),
        Length(max=120)
    ])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Login')

    def validate_email(self, field):
        """Check if email exists and account status"""
        user = User.query.filter_by(email=field.data.lower()).first()
        if user and user.is_deleted:
            raise ValidationError('This account has been deleted. Please register a new account or contact support for account restoration.')

class RegistrationForm(FlaskForm):
    """Form for new user registration"""
    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=2, max=50)
    ])
    email = StringField('Email', validators=[
        DataRequired(),
        Email(),
        Length(max=120)
    ])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Register')

    def validate_email(self, email):
        """Check if email is available for registration"""
        user = User.query.filter_by(email=email.data.lower()).first()
        if user:
            if user.is_deleted:
                # If the account is deleted, allow re-registration
                user.restore_account()
                db.session.delete(user)
                db.session.commit()
            else:
                raise ValidationError('Email already registered. Please use a different email or login to your existing account.')

class RequestPasswordResetForm(FlaskForm):
    """Form for requesting a password reset"""
    email = StringField('Email', validators=[
        DataRequired(),
        Email(),
        Length(max=120)
    ])
    submit = SubmitField('Request Password Reset')

class ResetPasswordForm(FlaskForm):
    """Form for resetting password with token"""
    password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Reset Password')

class VerifyMFAForm(FlaskForm):
    """Form for verifying MFA token"""
    token = StringField('Enter 6-digit code', validators=[
        DataRequired(),
        Length(min=6, max=6, message='Code must be 6 digits')
    ])
    submit = SubmitField('Verify')

class SetupMFAForm(FlaskForm):
    """Form for setting up MFA"""
    token = StringField('Enter the 6-digit code from your authenticator app', validators=[
        DataRequired(),
        Length(min=6, max=6, message='Code must be 6 digits')
    ])
    submit = SubmitField('Enable MFA')