"""Authentication routes for login and registration"""
import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash
from models import db, User
from forms.auth import LoginForm, RegistrationForm


# Configure logging
logger = logging.getLogger(__name__)

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    try:
        if current_user.is_authenticated:
            logger.info(f"User {current_user.email} redirected to dashboard")
            return redirect(url_for('main.dashboard'))

        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(email=form.email.data).first()
            if user and user.check_password(form.password.data):
                login_user(user)
                logger.info(f"User {user.email} logged in successfully")
                return redirect(url_for('main.dashboard'))
            flash('Invalid email or password')
            logger.warning(f"Failed login attempt for email: {form.email.data}")
        return render_template('auth/login.html', form=form)
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        flash('An error occurred during login')
        return render_template('auth/login.html', form=form)

@auth.route('/register', methods=['GET', 'POST'])
def register():
    """Handle user registration with enhanced logging"""
    logger.debug("Entering registration route")

    if current_user.is_authenticated:
        logger.debug(f"Already authenticated user {current_user.id} attempting to access registration")
        return redirect(url_for('main.index'))

    try:
        form = RegistrationForm()
        logger.debug("Registration form instantiated")

        if form.validate_on_submit():
            try:
                user = User(
                    email=form.email.data.lower(),
                    username=form.username.data,
                    is_admin=False
                )
                user.set_password(form.password.data)
                db.session.add(user)
                db.session.commit()

                # Create default accounts for the new user
                User.create_default_accounts(user.id)

                logger.info(f"New user registered successfully: {form.email.data}")
                flash('Registration successful! Please login.', 'success')
                return redirect(url_for('auth.login'))
            except Exception as e:
                logger.error(f"Error registering user: {str(e)}")
                db.session.rollback()
                flash('Registration failed. Please try again.', 'error')

        return render_template('auth/register.html', form=form)
    except Exception as e:
        logger.error(f"Registration route error: {str(e)}")
        flash('An error occurred during registration', 'error')
        return render_template('auth/register.html', form=form)

@auth.route('/logout')
@login_required
def logout():
    """Handle user logout"""
    try:
        user_email = current_user.email
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