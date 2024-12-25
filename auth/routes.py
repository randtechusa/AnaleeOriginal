"""
Authentication routes including password reset and MFA functionality
"""
import qrcode
import io
import base64
from flask import (
    Blueprint, render_template, redirect, url_for, flash,
    current_app, request, session
)
from flask_login import current_user, login_required, login_user
from flask_mail import Message
from models import db, User
from forms.auth import (
    RequestPasswordResetForm, ResetPasswordForm,
    VerifyMFAForm, SetupMFAForm, LoginForm, RegistrationForm
)

auth = Blueprint('auth', __name__)

def send_reset_email(user):
    """Send password reset email to user"""
    token = user.generate_reset_token()
    msg = Message(
        'Password Reset Request',
        sender=current_app.config['MAIL_DEFAULT_SENDER'],
        recipients=[user.email]
    )
    reset_url = url_for('auth.reset_password', token=token, _external=True)
    msg.html = render_template(
        'email/password_reset.html',
        user=user,
        reset_url=reset_url
    )
    current_app.mail.send(msg)

@auth.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    """Handle password reset requests"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = RequestPasswordResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_reset_email(user)
            flash('Check your email for instructions to reset your password', 'info')
            return redirect(url_for('auth.login'))
        else:
            flash('Email address not found', 'error')

    return render_template('auth/reset_password_request.html', form=form)

@auth.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Handle password reset with token"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    user = User.query.filter_by(reset_token=token).first()
    if not user or not user.verify_reset_token(token):
        flash('Invalid or expired reset token', 'error')
        return redirect(url_for('auth.reset_password_request'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        user.clear_reset_token()
        db.session.commit()
        flash('Your password has been reset', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', form=form)

@auth.route('/setup_mfa', methods=['GET', 'POST'])
@login_required
def setup_mfa():
    """Handle MFA setup"""
    if current_user.mfa_enabled:
        flash('MFA is already enabled', 'info')
        return redirect(url_for('main.index'))

    form = SetupMFAForm()

    # Generate MFA secret if not exists
    if not current_user.mfa_secret:
        current_user.generate_mfa_secret()
        db.session.commit()

    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(current_user.get_totp_uri())
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    # Convert image to base64
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_str = f"data:image/png;base64,{base64.b64encode(img_buffer.getvalue()).decode()}"

    if form.validate_on_submit():
        if current_user.verify_totp(form.token.data):
            current_user.mfa_enabled = True
            db.session.commit()
            flash('MFA has been enabled successfully', 'success')
            return redirect(url_for('main.index'))
        else:
            flash('Invalid verification code', 'error')

    return render_template(
        'auth/setup_mfa.html',
        form=form,
        qr_code=img_str,
        secret_key=current_user.mfa_secret
    )

@auth.route('/verify_mfa', methods=['GET', 'POST'])
def verify_mfa():
    """Handle MFA verification during login"""
    if not session.get('mfa_user_id'):
        return redirect(url_for('auth.login'))

    form = VerifyMFAForm()
    if form.validate_on_submit():
        user = User.query.get(session['mfa_user_id'])
        if user and user.verify_totp(form.token.data):
            login_user(user)
            session.pop('mfa_user_id', None)
            next_page = session.pop('next', None)
            return redirect(next_page or url_for('main.index'))
        else:
            flash('Invalid verification code', 'error')

    return render_template('auth/verify_mfa.html', form=form)


from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from forms.auth import LoginForm, RegistrationForm
from models import db, User

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.index'))
        flash('Invalid email or password', 'error')

    return render_template('auth/login.html', form=form)

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data
        )
        user.set_password(form.password.data)
        db.session.add(user)
        try:
            db.session.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash('Registration failed. Please try again.', 'error')

    return render_template('auth/register.html', form=form)