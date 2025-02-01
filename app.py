
"""Main application factory with enhanced logging and protection"""
import os
import logging
from datetime import datetime
from flask import Flask, render_template, request
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from models import db, User
from config import config

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[logging.FileHandler('app.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

login_manager = LoginManager()
csrf = CSRFProtect()

def create_app(config_name='development'):
    """Create and configure Flask application"""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config[config_name])
    
    # Ensure instance directory exists with proper permissions
    instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
    os.makedirs(instance_path, exist_ok=True)
    os.chmod(instance_path, 0o777)  # Ensure write permissions
    app.instance_path = instance_path
    
    # Initialize extensions
    _init_extensions(app)
    _register_blueprints(app)
    
    with app.app_context():
        db.create_all()
    _register_error_handlers(app)
    
    return app

def _init_extensions(app):
    """Initialize Flask extensions"""
    db.init_app(app)
    Migrate(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    csrf.init_app(app)

def _create_instance_path(app):
    """Create instance folder"""
    os.makedirs(app.instance_path, exist_ok=True)

def _setup_development_db(app):
    """Configure database for development"""
    if app.config['ENV'] == 'development':
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(app.instance_path, "dev.db")}'

def _register_blueprints(app):
    """Register application blueprints"""
    with app.app_context():
        from auth.routes import auth
        from main.routes import main
        from historical_data import historical_data
        from bank_statements import bank_statements
        from reports import reports
        from chat import chat
        from errors import errors
        from admin import admin

        blueprints = [
            (auth, "Authentication"),
            (main, "Main Application"),
            (historical_data, "Historical Data"),
            (bank_statements, "Bank Statements"),
            (reports, "Reports"),
            (chat, "Chat"),
            (admin, "Admin"),
            (errors, "Error Handling")
        ]

        for blueprint, _ in blueprints:
            app.register_blueprint(blueprint)

        db.create_all()

def _register_error_handlers(app):
    """Register error handlers"""
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('error.html', error=error), 500

    @app.errorhandler(Exception)
    def handle_exception(error):
        db.session.rollback()
        return render_template('error.html', error=error), 500

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

if __name__ == '__main__':
    app = create_app('production')
    port = int(os.environ.get('PORT', 80))
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False
    )
