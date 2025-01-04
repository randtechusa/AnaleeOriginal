"""Authentication routes for login and registration"""
import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash
from models import db, User

# Configure logging
logger = logging.getLogger(__name__)

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').lower().strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)

        if not email or not password:
            flash('Please fill in all fields.', 'error')
            return render_template('auth/login.html')

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user, remember=remember)
            logger.info(f"User {user.email} logged in successfully")
            flash('Logged in successfully!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.index'))
        else:
            logger.warning(f"Failed login attempt for email: {email}")
            flash('Invalid email or password.', 'error')

    return render_template('auth/login.html')

@auth.route('/register', methods=['GET', 'POST'])
def register():
    """Handle user registration"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').lower().strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not email or not username or not password:
            flash('Please fill in all fields.', 'error')
            return render_template('auth/register.html')

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return render_template('auth/register.html')

        try:
            user = User(
                email=email,
                username=username,
                is_admin=False
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            logger.info(f"New user registered successfully: {email}")
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            logger.error(f"Error registering user: {str(e)}")
            db.session.rollback()
            flash('Registration failed. Please try again.', 'error')

    return render_template('auth/register.html')

@auth.route('/logout')
@login_required
def logout():
    """Handle user logout with proper cleanup"""
    try:
        user_email = current_user.email
        logout_user()
        session.clear()
        logger.info(f"User {user_email} logged out successfully")
        flash('You have been logged out.', 'info')
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

            # Log the admin credentials for easy access
            logger.info("Default admin credentials:")
            logger.info("Email: admin@example.com")
            logger.info("Password: admin123")
            return True
        return True
    except Exception as e:
        logger.error(f"Error creating admin user: {str(e)}")
        db.session.rollback()
        return False