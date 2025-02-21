"""Main application factory with enhanced database management"""
import os
import logging
import time
from flask import Flask, redirect, url_for
from sqlalchemy import text
from extensions import db, init_extensions
from config import get_config

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def init_database(app):
    """Initialize database with comprehensive error handling and health monitoring"""
    from utils.db_health import DatabaseHealth
    import time

    logger.info("Starting database initialization...")

    if 'sqlite' in app.config['SQLALCHEMY_DATABASE_URI'].lower():
        logger.info("Using SQLite database")
        with app.app_context():
            db.create_all()
            return True

    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            with app.app_context():
                db.create_all()
                db.session.execute(text('SELECT 1'))
                db.session.commit()
                logger.info("Database initialized successfully")
                return True
        except Exception as e:
            retry_count += 1
            logger.error(f"Database initialization attempt {retry_count} failed: {e}")
            if retry_count < max_retries:
                time.sleep(2 ** retry_count)  # Exponential backoff
            else:
                logger.info("Falling back to SQLite database")
                app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/app.db'
                with app.app_context():
                    db.create_all()
                    return True
    return False


def create_app(config_name=None):
    """Create and configure Flask application"""
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')

    try:
        app = Flask(__name__)

        # Load configuration
        config = get_config(config_name)
        app.config.from_object(config)

        # Initialize extensions
        init_extensions(app)

        # Initialize database
        if not init_database(app):
            logger.error("Failed to initialize database")
            return None

        # Register blueprints
        with app.app_context():
            from main import bp as main_bp
            app.register_blueprint(main_bp)

            from auth import bp as auth_bp
            app.register_blueprint(auth_bp, url_prefix='/auth')

            from admin import bp as admin_bp
            app.register_blueprint(admin_bp, url_prefix='/admin')

            from reports import reports as reports_bp
            app.register_blueprint(reports_bp, url_prefix='/reports')

            from risk_assessment import risk_assessment as risk_bp
            app.register_blueprint(risk_bp)

            from historical_data import historical_data as historical_bp
            app.register_blueprint(historical_bp)

            @app.route('/')
            def index():
                return redirect(url_for('main.index'))

        return app

    except Exception as e:
        logger.error(f"Application creation failed: {str(e)}", exc_info=True)
        return None

if __name__ == '__main__':
    app = create_app()
    if app:
        port = int(os.environ.get('PORT', 8080))
        app.run(host='0.0.0.0', port=port)
    else:
        logger.error("Failed to create application")