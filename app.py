"""Main application factory with enhanced logging and protection"""
import os
import logging
from datetime import datetime
from flask import Flask, render_template, request, flash, redirect, url_for
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import text
from models import db, User

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
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
    """Create and configure Flask application with improved error handling"""
    app = Flask(__name__)
    logger.info(f"Starting application with config: {config_name}")

    try:
        # Load configuration
        if isinstance(config_name, str):
            app.config.from_object(f'config.{config_name.capitalize()}Config')
        else:
            app.config.from_object(config_name)

        # Initialize extensions
        db.init_app(app)
        Migrate(app, db)
        login_manager.init_app(app)
        csrf.init_app(app)

        login_manager.login_view = 'auth.login'

        # Test database connection
        with app.app_context():
            try:
                logger.info("Testing database connection...")
                db.session.execute(text('SELECT 1'))
                db.create_all()
                logger.info("Database initialized successfully")
            except Exception as e:
                logger.error(f"Database initialization error: {str(e)}")
                if 'sqlite' not in app.config['SQLALCHEMY_DATABASE_URI']:
                    logger.info("Switching to SQLite fallback database")
                    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/dev.db'
                    db.init_app(app)
                    db.create_all()

        # Register blueprints
        blueprints = [
            ('main.routes', 'main', ""),
            ('auth.routes', 'auth', "/auth"),
            ('admin.routes', 'admin', "/admin"),
            ('chat.routes', 'chat', "/chat"),
            ('historical_data.routes', 'historical_data', "/historical"),
            ('recommendations.routes', 'recommendations', "/recommendations"),
            ('risk_assessment.routes', 'risk_assessment', "/risk"),
            ('reports.routes', 'reports', "/reports"),
            ('suggestions.routes', 'suggestions', "/suggestions")
        ]

        for module, name, url_prefix in blueprints:
            try:
                bp = __import__(module, fromlist=['bp']).bp
                app.register_blueprint(bp, url_prefix=url_prefix)
                logger.info(f"Registered blueprint {name} at {url_prefix}")
            except Exception as e:
                logger.error(f"Error registering blueprint {name}: {str(e)}")


        @app.errorhandler(500)
        def internal_error(error):
            logger.error(f"Internal Server Error: {error}")
            db.session.rollback()
            return render_template('error.html', error="An internal error occurred."), 500

        @app.errorhandler(404)
        def not_found_error(error):
            return render_template('error.html', error="Page not found"), 404

        return app

    except Exception as e:
        logger.error(f"Application creation failed: {str(e)}")
        raise

@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except Exception as e:
        logger.error(f"Error loading user {user_id}: {str(e)}")
        return None

if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)