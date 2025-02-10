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
from werkzeug.utils import secure_filename

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

        # Load configuration
        app.config.from_object(f'config.{config_name.capitalize()}Config')

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
                db.session.commit()
                logger.info("Database connection successful")

                try:
                    db.create_all()
                    logger.info("Database tables created successfully")
                except Exception as e:
                    logger.error(f"Error creating tables: {str(e)}")
                    raise
            except Exception as e:
                logger.error(f"Database error: {str(e)}")
                db.session.remove()

                # Fallback to SQLite if needed
                if 'sqlite' not in app.config['SQLALCHEMY_DATABASE_URI']:
                    logger.info("Switching to SQLite fallback database")
                    sqlite_path = os.path.join(app.instance_path, 'dev.db')
                    os.makedirs(app.instance_path, exist_ok=True)
                    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{sqlite_path}'

                    db.init_app(app)
                    with app.app_context():
                        db.create_all()
                        logger.info(f"Successfully initialized SQLite database at {sqlite_path}")

        # Import and register blueprints
        from main.routes import main
        from auth.routes import auth
        from admin.routes import admin
        from chat.routes import chat
        from historical_data.routes import historical_data
        from recommendations.routes import recommendations
        from risk_assessment.routes import risk_assessment
        from reports.routes import reports
        from suggestions.routes import suggestions

        # Register blueprints
        blueprints = [
            (main, ""),
            (auth, "/auth"),
            (admin, "/admin"),
            (chat, "/chat"),
            (historical_data, "/historical"),
            (recommendations, "/recommendations"),
            (risk_assessment, "/risk"),
            (reports, "/reports"),
            (suggestions, "/suggestions")
        ]

        for blueprint, url_prefix in blueprints:
            try:
                app.register_blueprint(blueprint, url_prefix=url_prefix)
                logger.info(f"Registered blueprint at {url_prefix}")
            except Exception as e:
                logger.error(f"Error registering blueprint for {url_prefix}: {str(e)}")

        # Error handlers
        @app.errorhandler(500)
        def internal_error(error):
            logger.error(f"Internal Server Error: {error}")
            db.session.rollback()
            return render_template('error.html', error="An internal error occurred. Please try again."), 500

        @app.errorhandler(404)
        def not_found_error(error):
            return render_template('error.html', error="Page not found"), 404

        return app

    except Exception as e:
        logger.error(f"Application creation failed: {str(e)}")
        raise

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID with error handling"""
    try:
        return User.query.get(int(user_id))
    except Exception as e:
        logger.error(f"Error loading user {user_id}: {str(e)}")
        return None

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)