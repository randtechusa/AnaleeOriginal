"""Main routes for the application"""
from flask import Blueprint, render_template
from flask_login import login_required

main = Blueprint('main', __name__)

@main.route('/')
@main.route('/index')
@login_required
def index():
    return render_template('index.html')

@main.route('/admin_dashboard')
@login_required
def admin_dashboard():
    return render_template('admin/dashboard.html')
