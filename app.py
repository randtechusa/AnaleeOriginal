"""Main application factory with enhanced logging and protection"""
import os
import logging
from flask import Flask, render_template, request, session
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from models import db, User
from werkzeug.middleware.proxy_fix import ProxyFix

# Enhanced logging configuration
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.FileHandler('debug.log'),
        logging.StreamHandler()
    ]
)

# Add separate debug log for blueprint operations
debug_handler = logging.FileHandler('blueprint_debug.log')
debug_handler.setLevel(logging.DEBUG)
debug_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
))
blueprint_logger = logging.getLogger('blueprint.operations')
blueprint_logger.addHandler(debug_handler)
blueprint_logger.setLevel(logging.DEBUG)

# Add error log
error_handler = logging.FileHandler('error.log')
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
))
logging.getLogger('').addHandler(error_handler)

# Add request logging
werkzeug_log = logging.getLogger('werkzeug')
werkzeug_log.setLevel(logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask extensions 
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect() # Added CSRF protection

def create_app():
    """Create and configure Flask application with enhanced logging"""
    logger.info("Starting application creation...")
    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # Basic configuration with logging
    logger.info("Configuring application with database connection...")

    # Database configuration with retries
    max_retries = 5
    retry_count = 0
    while retry_count < max_retries:
        try:
            db_url = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
            app.config['SQLALCHEMY_DATABASE_URI'] = db_url
            app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
            app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(32))
            app.config['WTF_CSRF_ENABLED'] = True
            app.config['SESSION_COOKIE_SECURE'] = True
            app.config['SESSION_COOKIE_HTTPONLY'] = True

            # Test database connection
            db.init_app(app)
            with app.app_context():
                try:
                    db.engine.connect()
                    db.engine.dispose()
                except Exception as e:
                    logger.error(f"Database connection error: {str(e)}")
                    raise
            logger.info("Database connection verified")
            break

        except Exception as e:
            retry_count += 1
            logger.warning(f"Database connection attempt {retry_count} failed: {str(e)}")
            if retry_count == max_retries:
                logger.error(f"Database connection failed after {max_retries} attempts: {str(e)}")
                logger.error("Failed to establish database connection")
                raise

    # Initialize other extensions
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    csrf.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return User.query.get(int(user_id))
        except Exception as e:
            logger.error(f"Error loading user {user_id}: {str(e)}")
            return None

    # Register blueprints with enhanced logging and error handling
    try:
        from auth.routes import auth
        from main.routes import main
        from historical_data import historical_data
        from bank_statements import bank_statements
        from reports import reports
        from chat import chat
        from errors import errors

        # Log blueprint registration details
        blueprint_logger.info("Starting blueprint registration process...")

        blueprints = [
            (auth, "Authentication"),
            (main, "Main Application"),
            (historical_data, "Historical Data"),
            (bank_statements, "Bank Statements"),
            (reports, "Reports"),
            (chat, "Chat"),
            (errors, "Error Handling")
        ]

        for blueprint, name in blueprints:
            try:
                blueprint_logger.debug(f"Registering {name} blueprint...")
                app.register_blueprint(blueprint)
                blueprint_logger.info(f"Successfully registered {name} blueprint")

                # Log registered routes for debugging
                routes = [str(rule) for rule in app.url_map.iter_rules() 
                         if rule.endpoint.startswith(blueprint.name + '.')]
                blueprint_logger.debug(f"Registered routes for {name}: {routes}")

            except Exception as e:
                blueprint_logger.error(f"Error registering {name} blueprint: {str(e)}")
                raise

        logger.info("All blueprints registered successfully")

    except Exception as e:
        logger.error(f"Critical error during blueprint registration: {str(e)}")
        raise

    # Verify database tables
    with app.app_context():
        try:
            db.create_all()
            logger.info("Database tables verified")
        except Exception as e:
            logger.error(f"Error verifying database tables: {str(e)}")
            raise

    # Register error handlers
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()  # Roll back any failed database transactions
        logger.error(f"Internal Server Error: {str(error)}")
        return render_template('error.html', error=error), 500

    @app.errorhandler(Exception)
    def handle_exception(error):
        db.session.rollback()
        logger.error(f"Unhandled Exception: {str(error)}", exc_info=True)
        logger.debug(f"Request path: {request.path}")
        logger.debug(f"Request method: {request.method}")
        logger.debug(f"Request headers: {dict(request.headers)}")
        return render_template('error.html', error=error), 500

    logger.info("Flask application created successfully")
    return app

if __name__ == '__main__':
    app = create_app()
    port = 8080
    logger.info(f"Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)