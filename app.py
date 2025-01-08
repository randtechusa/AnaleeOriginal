"""Main application configuration and initialization"""
import os
import logging
import sys
from datetime import datetime
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
    try:
        app = Flask(__name__)

        # Basic configuration
        app.config.update({
            'SECRET_KEY': os.environ.get('FLASK_SECRET_KEY', os.urandom(32)),
            'SQLALCHEMY_DATABASE_URI': os.environ.get('DATABASE_URL', 'sqlite:///app.db'),
            'SQLALCHEMY_TRACK_MODIFICATIONS': False
        })

        # Initialize extensions
        db.init_app(app)
        migrate.init_app(app, db)
        login_manager.init_app(app)
        login_manager.login_view = 'auth.login'

        # User loader callback
        @login_manager.user_loader
        def load_user(user_id):
            return User.query.get(int(user_id))

        # Register blueprints
        from auth.routes import auth
        from main.routes import main

        app.register_blueprint(auth)
        app.register_blueprint(main)

        # Create database tables and admin user
        with app.app_context():
            db.create_all()
            from auth.routes import create_admin_if_not_exists
            create_admin_if_not_exists()

        return app

    except Exception as e:
        logger.error(f"Error in application creation: {str(e)}")
        return None

if __name__ == '__main__':
    app = create_app()
    if app:
        port = int(os.environ.get('PORT', 8080))
        app.run(host='0.0.0.0', port=port)
    else:
        logger.error("Application creation failed")
        sys.exit(1)