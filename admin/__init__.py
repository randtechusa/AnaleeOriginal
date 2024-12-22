"""
Admin module for managing subscriptions and system-wide settings
This module is completely separate from core features to ensure their protection
"""
from flask import Blueprint, abort, redirect, url_for
from flask_login import login_required, current_user
from functools import wraps

admin = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    """Decorator to protect admin routes"""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    return decorated_function

# Import routes after blueprint creation to avoid circular imports
from . import routes

# Protect all admin routes with admin_required decorator
@admin.before_request
def restrict_admin_access():
    """Ensure only admin users can access admin routes"""
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)