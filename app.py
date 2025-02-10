"""Main application factory with enhanced logging and protection"""
import os
import logging
from flask import Flask, render_template, flash, redirect, url_for
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import text
from models import db, User

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

login_manager = LoginManager()
csrf = CSRFProtect()

def create_app(config_name='development'):
    """Create and configure Flask application"""
    try:
        app = Flask(__name__)

        # Load configuration
        app.config.from_object(f'config.{config_name.capitalize()}Config')

        # Initialize extensions
        db.init_app(app)
        Migrate(app, db)
        login_manager.init_app(app)
        csrf.init_app(app)

        login_manager.login_view = 'auth.login'

        # Initialize database
        with app.app_context():
            db.create_all()

        # Register blueprints
        from main import bp as main_bp
        app.register_blueprint(main_bp)

        from auth import bp as auth_bp
        app.register_blueprint(auth_bp)

        from admin import bp as admin_bp
        app.register_blueprint(admin_bp, url_prefix='/admin')

        from errors import bp as errors_bp
        app.register_blueprint(errors_bp)

        @app.errorhandler(404)
        def not_found_error(error):
            return render_template('error.html', error="Page not found"), 404

        @app.errorhandler(500)
        def internal_error(error):
            db.session.rollback()
            return render_template('error.html', error="An internal error occurred"), 500

        return app

    except Exception as e:
        logger.error(f"Application creation failed: {str(e)}")
        raise

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login"""
    try:
        return User.query.get(int(user_id))
    except Exception as e:
        logger.error(f"Error loading user {user_id}: {str(e)}")
        return None

if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)