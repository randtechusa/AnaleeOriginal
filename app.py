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
    import time
    from sqlalchemy import text
    from utils.db_health import DatabaseHealth

    logger.info("Starting database initialization...")
    db_health = DatabaseHealth.get_instance()

    # Check if we're already configured for SQLite
    if 'sqlite' in app.config['SQLALCHEMY_DATABASE_URI'].lower():
        logger.info("Using SQLite database")
        try:
            # Create tables within app context - db.init_app is already called in init_extensions
            with app.app_context():
                db.create_all()
                db.session.execute(text('SELECT 1'))
                db.session.commit()
                logger.info("SQLite database tables created successfully")
                return True
        except Exception as e:
            logger.error(f"SQLite initialization failed: {e}")
            return False

    # PostgreSQL initialization with better error handling
    max_retries = 3
    retry_count = 0
    
    # Store original PostgreSQL URI for potential wake-up attempts
    original_uri = app.config['SQLALCHEMY_DATABASE_URI']
    endpoint_disabled = False

    while retry_count < max_retries:
        try:
            with app.app_context():
                db.create_all()
                db.session.execute(text('SELECT 1'))
                db.session.commit()
                logger.info("PostgreSQL database initialized successfully")
                return True
        except Exception as e:
            error_str = str(e).lower()
            retry_count += 1
            
            # Detect if the PostgreSQL endpoint is disabled
            if 'endpoint is disabled' in error_str:
                endpoint_disabled = True
                logger.warning("PostgreSQL endpoint appears to be disabled")
                
                # Try to wake up the endpoint if this is our first or second attempt
                if retry_count < max_retries:
                    logger.info(f"Attempting to wake up PostgreSQL endpoint (attempt {retry_count})")
                    wake_success = db_health.wake_up_endpoint(original_uri)
                    if wake_success:
                        logger.info("Successfully woke up endpoint, retrying connection")
                        continue
            
            logger.error(f"Database initialization attempt {retry_count} failed: {e}")
            
            if retry_count < max_retries:
                # Exponential backoff with a bit of jitter
                delay = (2 ** retry_count) + (time.time() % 1)
                logger.info(f"Retrying in {delay:.1f} seconds...")
                time.sleep(delay)
            else:
                # Final attempt failed, fall back to SQLite
                logger.info("All PostgreSQL connection attempts failed. Falling back to SQLite database")
                
                if endpoint_disabled:
                    logger.info("Consider enabling the PostgreSQL endpoint in the Replit Database panel")
                
                # Use instance/dev.db for consistency with the rest of the application
                app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/dev.db'
                # Completely close any existing connections before switching
                db.get_engine().dispose()
                
                try:
                    with app.app_context():
                        db.create_all()
                        db.session.execute(text('SELECT 1'))
                        db.session.commit()
                        logger.info("Fallback to SQLite successful")
                        return True
                except Exception as fallback_error:
                    logger.error(f"SQLite fallback failed: {fallback_error}")
                    return False
    
    logger.critical("Failed to initialize database after maximum retries")
    return False

def health_check_routine():
    """Periodic health check for database connections"""
    import threading
    from utils.db_health import DatabaseHealth
    import time
    
    db_health = DatabaseHealth.get_instance()
    
    def _check_periodically():
        while True:
            try:
                # Check connection
                success, error = db_health.check_connection()
                
                # If the check failed and we should initiate failover
                if not success and db_health.should_failover():
                    logger.warning("Database health check failed, initiating failover procedure")
                    failover_success, failover_error = db_health.perform_failover()
                    if failover_success:
                        logger.info("Database failover completed successfully")
                    else:
                        logger.error(f"Database failover failed: {failover_error}")
                
                # Sleep for 5 minutes between checks (adjust as needed)
                time.sleep(300)
            except Exception as e:
                logger.error(f"Error in health check routine: {str(e)}")
                # Sleep a bit and try again
                time.sleep(60)
    
    # Start health check in background thread
    health_thread = threading.Thread(target=_check_periodically, daemon=True)
    health_thread.start()
    logger.info("Database health check routine started")


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
        # Start database health check routine in production mode
        if not app.debug or os.environ.get('FLASK_ENV') == 'production':
            health_check_routine()
            
        # Always use port 5000 on Replit, which is the non-firewalled port
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port, debug=True)
    else:
        logger.error("Failed to create application")