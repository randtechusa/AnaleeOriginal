"""
Authentication routes including login, password reset and MFA functionality
"""
import logging
from flask import (
    render_template, redirect, url_for, flash,
    request, session, current_app
)
from flask_login import current_user, login_user, logout_user, login_required
from werkzeug.security import generate_password_hash
import qrcode
import io
import base64

from . import auth
from models import db, User
from forms.auth import (
    LoginForm, RequestPasswordResetForm, ResetPasswordForm, 
    VerifyMFAForm, SetupMFAForm, RegistrationForm
)

# Configure logging
logger = logging.getLogger(__name__)

@auth.route('/register', methods=['GET', 'POST'])
def register():
    """Handle new user registration"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            user = User(
                username=form.username.data,
                email=form.email.data.lower().strip(),
                subscription_status='pending'  # Set initial status as pending
            )
            user.set_password(form.password.data)

            db.session.add(user)
            db.session.commit()

            flash('Registration successful! Please wait for admin approval before logging in.', 'success')
            logger.info(f"New user registered: {user.email}")
            return redirect(url_for('auth.login'))

        except Exception as e:
            db.session.rollback()
            logger.error(f"Registration error: {str(e)}")
            flash('An error occurred during registration.', 'error')

    return render_template('auth/register.html', form=form)

def create_admin_if_not_exists():
    """Create admin user if it doesn't exist"""
    try:
        # Check if admin exists
        admin = User.query.filter_by(email='festusa@cnbs.co.za').first()
        if not admin:
            # Create new admin user with proper fields
            admin = User(
                username='admin',
                email='festusa@cnbs.co.za',
                is_admin=True,
                subscription_status='active'
            )
            # Set password with proper hashing
            admin.set_password('admin123')

            # Add and commit to database
            db.session.add(admin)
            db.session.commit()
            logger.info("Admin user created successfully")
            return True
        return True
    except Exception as e:
        logger.error(f"Error creating admin user: {str(e)}")
        # Rollback on error
        db.session.rollback()
        return False

@auth.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login with enhanced security and session management."""
    try:
        # If user is already authenticated, redirect appropriately
        if current_user.is_authenticated:
            logger.info(f"Already authenticated user {current_user.id} redirected to appropriate dashboard")
            if current_user.is_admin:
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('main.dashboard'))

        form = LoginForm()
        if form.validate_on_submit():
            # Find and verify user
            user = User.query.filter_by(email=form.email.data.lower().strip()).first()

            if not user or not user.check_password(form.password.data):
                logger.warning(f"Failed login attempt for email: {form.email.data}")
                flash('Invalid email or password', 'error')
                return render_template('auth/login.html', form=form)

            # Handle MFA if enabled
            if user.mfa_enabled:
                session['mfa_user_id'] = user.id
                logger.info(f"MFA verification required for user {user.email}")
                return redirect(url_for('auth.verify_mfa'))

            # Only check subscription status for non-admin users
            if not user.is_admin:
                if user.subscription_status == 'pending':
                    logger.warning(f"Login attempt by pending user: {user.email}")
                    flash('Your account is pending approval.', 'warning')
                    return render_template('auth/login.html', form=form)

                if user.subscription_status == 'deactivated':
                    logger.warning(f"Login attempt by deactivated user: {user.email}")
                    flash('Your account has been deactivated.', 'error')
                    return render_template('auth/login.html', form=form)

            # Login successful
            login_user(user, remember=form.remember_me.data)
            logger.info(f"User {user.email} logged in successfully")

            # Redirect based on user type with proper flash message
            if user.is_admin:
                flash('Welcome back, Administrator!', 'success')
                return redirect(url_for('admin.dashboard'))
            flash('Login successful!', 'success')
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
    """Handle user logout with proper cleanup"""
    try:
        # Store user type before logout for proper message
        was_admin = current_user.is_admin
        user_email = current_user.email

        logout_user()
        session.clear()  # Clear all session data

        logger.info(f"User {user_email} logged out successfully")
        flash('You have been logged out successfully.', 'info')

    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        flash('Error during logout.', 'error')

    return redirect(url_for('auth.login'))

@auth.route('/setup_mfa', methods=['GET', 'POST'])
@login_required
def setup_mfa():
    """Handle MFA setup"""
    if current_user.mfa_enabled:
        flash('MFA is already enabled', 'info')
        return redirect(url_for('main.dashboard'))

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
            return redirect(url_for('main.dashboard'))
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

            if user.is_admin:
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('main.dashboard'))
        else:
            flash('Invalid verification code', 'error')

    return render_template('auth/verify_mfa.html', form=form)

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