"""
Authentication routes including login, password reset and MFA functionality
"""
import logging
from flask import (
    render_template, redirect, url_for, flash,
    request, session, current_app
)
from flask_login import current_user, login_user, logout_user, login_required
import qrcode
import io
import base64

from . import auth
from models import db, User
from forms.auth import LoginForm, RequestPasswordResetForm, ResetPasswordForm, VerifyMFAForm, SetupMFAForm

# Configure logging
logger = logging.getLogger(__name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login with enhanced security and session management."""
    if current_user.is_authenticated:
        logger.info(f"Already authenticated user {current_user.id} redirected to index")
        return redirect(url_for('main.index'))

    form = LoginForm()
    if form.validate_on_submit():
        try:
            # Find and verify user
            user = User.query.filter_by(email=form.email.data.strip()).first()
            if not user or not user.check_password(form.password.data):
                logger.warning(f"Failed login attempt for email: {form.email.data}")
                flash('Invalid email or password', 'error')
                return render_template('auth/login.html', form=form)

            # Check subscription status
            if user.subscription_status == 'pending':
                logger.warning(f"Login attempt by pending user: {user.email}")
                flash('Your account is pending approval.', 'warning')
                return render_template('auth/login.html', form=form)

            if user.subscription_status == 'deactivated':
                logger.warning(f"Login attempt by deactivated user: {user.email}")
                flash('Your account has been deactivated.', 'error')
                return render_template('auth/login.html', form=form)

            # Handle MFA if enabled
            if user.mfa_enabled:
                session['mfa_user_id'] = user.id
                logger.info(f"MFA verification required for user {user.email}")
                return redirect(url_for('auth.verify_mfa'))

            # Login successful
            login_user(user, remember=form.remember_me.data)
            logger.info(f"User {user.email} logged in successfully")

            # Redirect based on user type
            if user.is_admin:
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('main.dashboard'))

        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            db.session.rollback()
            flash('An error occurred during login.', 'error')

    # GET request or form validation failed
    return render_template('auth/login.html', form=form)

@auth.route('/logout')
@login_required
def logout():
    """Handle user logout"""
    try:
        logout_user()
        session.clear()
        flash('You have been logged out.', 'info')
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        flash('Error during logout.', 'error')

    return redirect(url_for('auth.login'))

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