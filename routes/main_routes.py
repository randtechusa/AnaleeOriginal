"""
Main routes for the application.
Contains all core functionality routes including:
- Analyze Data 
- Historic Data
- Charts of Accounts
- iCountant Assistant
"""
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import statistics

from flask import render_template, request, redirect, url_for, flash, jsonify, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import text
import pandas as pd

from models import (
    db, User, Account, Transaction, UploadedFile, 
    CompanySettings, HistoricalData, AlertHistory, AlertConfiguration, FinancialGoal
)
from ai_insights import FinancialInsightsGenerator
from alert_system import AlertSystem

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def index():
    """Home page route"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('main.login'))

def login():
    """Handle user login with enhanced error handling and session management."""
    if current_user.is_authenticated:
        logger.info(f"Already authenticated user {current_user.id} redirected to dashboard")
        return redirect(url_for('main.dashboard'))

    # Clear any existing session data
    session.clear()
    logger.info("Starting login process with cleared session")

    if request.method == 'POST':
        try:
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '')

            if not email or not password:
                logger.warning("Login attempt with missing credentials")
                flash('Please provide both email and password')
                return render_template('login.html')

            # Verify database connection before proceeding
            try:
                db.session.execute(text('SELECT 1'))
            except Exception as db_error:
                logger.error(f"Database connection error: {str(db_error)}")
                db.session.rollback()
                flash('Unable to connect to database. Please try again.')
                return render_template('login.html')

            # Find and verify user
            user = User.query.filter_by(email=email).first()
            if not user:
                logger.warning(f"Login attempt for non-existent user: {email}")
                flash('Invalid email or password')
                return render_template('login.html')

            if not user.check_password(password):
                logger.warning(f"Password verification failed for user: {email}")
                flash('Invalid email or password')
                return render_template('login.html')

            # Login successful - set up session
            login_user(user, remember=True)
            logger.info(f"User {email} logged in successfully")

            # Handle redirect
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('main.dashboard')

            logger.info(f"Login successful, redirecting to: {next_page}")
            return redirect(next_page)

        except Exception as e:
            logger.error(f"Error during login process: {str(e)}")
            logger.exception("Full login error stacktrace:")
            db.session.rollback()
            flash('An error occurred during login. Please try again.')
            return render_template('login.html')

    # GET request - show login form
    return render_template('login.html')

def register():
    """Handle user registration"""
    if request.method == 'POST':
        try:
            # Verify database connection first
            try:
                db.session.execute(text('SELECT 1'))
            except Exception as db_error:
                logger.error(f"Database connection failed during registration: {str(db_error)}")
                flash('Unable to connect to database. Please try again.')
                return render_template('register.html')

            # Get and validate form data
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '')

            if not username or not email or not password:
                logger.warning("Registration attempt with missing fields")
                flash('All fields are required')
                return render_template('register.html')

            # Create new user
            user = User(username=username, email=email)
            user.set_password(password)

            db.session.add(user)
            db.session.commit()

            # Create default Chart of Accounts
            User.create_default_accounts(user.id)

            # Log user in
            login_user(user)
            flash('Registration successful')
            return redirect(url_for('main.dashboard'))

        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            db.session.rollback()
            flash('Error during registration')
            return render_template('register.html')

    return render_template('register.html')

def dashboard():
    """Main dashboard view"""
    if not current_user.is_authenticated:
        return redirect(url_for('main.login'))

    company_settings = CompanySettings.query.filter_by(user_id=current_user.id).first()
    if not company_settings:
        flash('Please configure company settings first.')
        return redirect(url_for('main.company_settings'))

    # Get transactions and prepare dashboard data
    try:
        transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date.desc()).all()
        return render_template('dashboard.html', transactions=transactions)
    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        flash('Error loading dashboard')
        return render_template('dashboard.html')

@login_required
def upload():
    """Handle file upload for transaction processing"""
    try:
        if request.method == 'POST':
            if 'file' not in request.files:
                flash('No file uploaded', 'error')
                return redirect(url_for('main.upload'))

            file = request.files['file']
            if not file.filename:
                flash('No file selected', 'error')
                return redirect(url_for('main.upload'))

            # Create upload record
            upload_record = UploadedFile(
                filename=file.filename,
                user_id=current_user.id,
                upload_date=datetime.utcnow()
            )
            db.session.add(upload_record)
            db.session.commit()

            flash('File uploaded successfully', 'success')
            return redirect(url_for('main.analyze', file_id=upload_record.id))

        # GET request - show upload form
        uploaded_files = UploadedFile.query.filter_by(user_id=current_user.id)\
            .order_by(UploadedFile.upload_date.desc())\
            .all()

        return render_template('upload.html', files=uploaded_files)

    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        db.session.rollback()
        flash('Error during file upload', 'error')
        return redirect(url_for('main.dashboard'))

@login_required
def analyze_list():
    """Display list of uploaded files available for analysis"""
    try:
        # Get uploaded files for current user
        files = UploadedFile.query.filter_by(user_id=current_user.id)\
            .order_by(UploadedFile.upload_date.desc())\
            .all()

        return render_template('analyze_list.html', files=files)
    except Exception as e:
        logger.error(f"Error accessing analyze list: {str(e)}")
        flash('Error loading analyze list', 'error')
        return redirect(url_for('main.dashboard'))

def logout():
    """Handle user logout"""
    logout_user()
    return redirect(url_for('main.login'))