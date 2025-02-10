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
        logger.info(f"Starting application with config: {config_name}")

        # Load configuration
        if isinstance(config_name, str):
            app.config.from_object(f'config.{config_name.capitalize()}Config')
        else:
            app.config.update(config_name)

        # Initialize extensions
        db.init_app(app)
        Migrate(app, db)
        login_manager.init_app(app)
        csrf.init_app(app)

        login_manager.login_view = 'auth.login'
        login_manager.login_message = 'Please log in to access this page.'
        login_manager.login_message_category = 'info'

        # Initialize database
        with app.app_context():
            try:
                logger.info("Testing database connection...")
                db.session.execute(text('SELECT 1'))
                db.create_all()
                logger.info("Database initialized successfully")
            except Exception as e:
                logger.error(f"Database initialization error: {str(e)}")
                if 'sqlite' not in app.config['SQLALCHEMY_DATABASE_URI']:
                    logger.error("Error connecting to PostgreSQL, trying SQLite fallback...")
                    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/dev.db'
                    db.init_app(app)
                    db.create_all()
                    logger.info("SQLite fallback database initialized")
                else:
                    raise

        # Register blueprints
        logger.info("Registering blueprints...")

        # Main blueprint
        from main import bp as main_bp
        app.register_blueprint(main_bp)
        logger.info("Registered main blueprint")

        # Auth blueprint
        from auth import bp as auth_bp
        app.register_blueprint(auth_bp)
        logger.info("Registered auth blueprint")

        # Admin blueprint
        from admin import bp as admin_bp
        app.register_blueprint(admin_bp, url_prefix='/admin')
        logger.info("Registered admin blueprint")

        # Errors blueprint
        from errors import bp as errors_bp
        app.register_blueprint(errors_bp)
        logger.info("Registered errors blueprint")

        # Register error handlers
        @app.errorhandler(404)
        def not_found_error(error):
            logger.warning(f"404 error: {error}")
            return render_template('error.html', error="Page not found"), 404

        @app.errorhandler(500)
        def internal_error(error):
            logger.error(f"Internal Server Error: {error}")
            db.session.rollback()
            return render_template('error.html', error="An internal error occurred."), 500

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
    app.run(host='0.0.0.0', port=port, debug=True)