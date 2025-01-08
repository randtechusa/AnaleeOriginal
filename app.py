"""Main application configuration and initialization"""
import os
import logging
from flask import Flask
from flask_migrate import Migrate
from flask_login import LoginManager
from models import db, User
from sqlalchemy.exc import SQLAlchemyError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask extensions
migrate = Migrate()
login_manager = LoginManager()

def verify_db_connection(app):
    """Verify database connection"""
    try:
        with app.app_context():
            db.engine.connect()
            logger.info("Database connection successful")
            return True
    except SQLAlchemyError as e:
        logger.error(f"Database connection failed: {str(e)}")
        return False

def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)

    # Basic configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(32))
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return User.query.get(int(user_id))
        except Exception as e:
            logger.error(f"Error loading user {user_id}: {str(e)}")
            return None

    # Register blueprints
    from auth.routes import auth
    from main.routes import main
    app.register_blueprint(auth)
    app.register_blueprint(main)

    return app

if __name__ == '__main__':
    app = create_app()

    # Verify database connection before starting
    if not verify_db_connection(app):
        logger.error("Could not connect to database. Exiting...")
        exit(1)

    with app.app_context():
        try:
            # Initialize database tables
            db.create_all()
            logger.info("Database tables created successfully")

            # Create admin user if not exists
            from auth.routes import create_admin_if_not_exists
            if create_admin_if_not_exists():
                logger.info("Admin user verified/created successfully")
            else:
                logger.warning("Failed to verify/create admin user")

            # Start the server
            port = int(os.environ.get('PORT', 8080))
            app.run(host='0.0.0.0', port=port, debug=True)

        except Exception as e:
            logger.error(f"Error during startup: {str(e)}")
            raise