"""Main routes for the application"""
from flask import Blueprint, render_template
from flask_login import login_required

main = Blueprint('main', __name__)

@main.route('/')
@main.route('/index')
@login_required
def index():
    return render_template('index.html')

@main.route('/analyze_list')
@login_required
def analyze_list():
    """Route for analyze data menu - protected core functionality"""
    return render_template('analyze_list.html')

@main.route('/dashboard')
@login_required 
def dashboard():
    """Main dashboard route"""
    return render_template('dashboard.html')

@main.route('/admin_dashboard')
@login_required
def admin_dashboard():
    return render_template('admin/dashboard.html')
