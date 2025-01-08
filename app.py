"""Main application configuration and initialization"""
import os
import logging
from flask import Flask
from flask_migrate import Migrate
from flask_login import LoginManager
from models import db, User

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask extensions
migrate = Migrate()
login_manager = LoginManager()

def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)

    # Basic configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(32))

    # Database configuration with fallback
    db_url = os.environ.get('DATABASE_URL', 'sqlite:///fallback.db')
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_POOL_SIZE'] = 5
    app.config['SQLALCHEMY_MAX_OVERFLOW'] = 10
    app.config['SQLALCHEMY_POOL_TIMEOUT'] = 30
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

    # Initialize database and create admin user
    with app.app_context():
        try:
            # Create all database tables
            db.create_all()
            logger.info("Database tables created successfully")

            # Create admin user
            from auth.routes import create_admin_if_not_exists
            if create_admin_if_not_exists():
                logger.info("Admin user setup completed")

        except Exception as e:
            logger.error(f"Database initialization error: {str(e)}")
            raise

    # Run the application on port 8080
    port = int(os.environ.get('PORT', 80))
    app.run(host='0.0.0.0', port=port, debug=False)