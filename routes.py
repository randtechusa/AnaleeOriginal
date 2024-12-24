"""Main application routes including authentication and core functionality"""
import logging
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, login_user, logout_user, current_user
from werkzeug.security import check_password_hash

from models import User, db
from forms import LoginForm

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create blueprint
main = Blueprint('main', __name__)

@main.route('/')
def index():
    """Root route - redirects to appropriate dashboard based on user type"""
    if current_user.is_authenticated:
        logger.info(f"User {current_user.email} redirected to dashboard")
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('main.login'))

@main.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login with enhanced error handling"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            logger.info(f"User {form.email.data} logged in successfully")
            return redirect(url_for('main.dashboard'))

        flash('Invalid email or password', 'error')
        return redirect(url_for('main.login'))

    return render_template('login.html', form=form)

@main.route('/dashboard')
@login_required
def dashboard():
    """Display user dashboard"""
    return render_template('dashboard.html')

@main.route('/logout')
@login_required
def logout():
    """Handle user logout"""
    logout_user()
    return redirect(url_for('main.login'))