"""Authentication routes for login and registration"""
import logging
from flask import render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user
from werkzeug.security import generate_password_hash
from models import db, User
from forms.auth import LoginForm, RegistrationForm
from auth import bp

# Configure logging
logger = logging.getLogger(__name__)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login with proper validation and error handling"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()

        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash('Account is deactivated. Please contact support.', 'error')
                return render_template('auth/login.html', form=form)

            login_user(user, remember=form.remember_me.data)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('main.dashboard'))

        flash('Invalid email or password.', 'error')

    return render_template('auth/login.html', form=form)

@bp.route('/register', methods=['GET', 'POST'])
def register():
    """Handle user registration with enhanced logging"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    form = RegistrationForm()
    if form.validate_on_submit():
        existing_user = User.query.filter_by(email=form.email.data.lower()).first()
        if existing_user:
            flash('Email already registered. Please use a different email.', 'error')
            return render_template('auth/register.html', form=form)

        user = User(
            username=form.username.data,
            email=form.email.data.lower(),
            is_admin=False,
            is_active=True
        )
        user.set_password(form.password.data)
        db.session.add(user)

        try:
            db.session.commit()
            logger.info(f"New user registered successfully: {form.email.data}")
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            logger.error(f"Database error during user registration: {str(e)}")
            db.session.rollback()
            flash('Database error during registration. Please try again.', 'error')

    return render_template('auth/register.html', form=form)

@bp.route('/logout')
def logout():
    """Handle user logout"""
    try:
        user_email = current_user.email if current_user.is_authenticated else 'Unknown'
        logout_user()
        session.clear()
        logger.info(f"User {user_email} logged out successfully")
        flash('You have been logged out.', 'success')
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        flash('Error during logout.', 'error')
    return redirect(url_for('auth.login'))

def create_admin_if_not_exists():
    """Create default admin user if not exists"""
    try:
        admin_email = "admin@example.com"
        admin = User.query.filter_by(email=admin_email).first()

        if not admin:
            admin = User(
                username="admin",
                email=admin_email,
                is_admin=True
            )
            admin.set_password("admin123")  # Default admin password
            db.session.add(admin)
            db.session.commit()
            logger.info("Admin user created successfully")
            return True
        return True
    except Exception as e:
        logger.error(f"Error creating admin user: {str(e)}")
        db.session.rollback()
        return False

from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user

def login_required_for_module(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this feature.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function