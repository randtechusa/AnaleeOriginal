from flask import render_template, redirect, url_for
from flask_login import login_required, current_user
from . import main

@main.route('/')
def index():
    """Landing page route"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))

@main.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard route"""
    return render_template('dashboard.html')
