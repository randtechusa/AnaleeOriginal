
"""Database migrations configuration"""
from flask import Flask
from flask_migrate import Migrate
from models import db
from config import get_config
import os

def init_migrations():
    """Initialize database migrations with enhanced error handling"""
    try:
        # Create Flask app with proper configuration
        app = Flask(__name__)
        app.config.from_object(get_config('development'))

        # Initialize database and migrations
        db.init_app(app)
        migrate = Migrate(app, db)

        with app.app_context():
            if 'sqlite' in app.config['SQLALCHEMY_DATABASE_URI']:
                db.create_all()
            else:
                migrate.init()

        return app, migrate
    except Exception as e:
        print(f"Error initializing migrations: {str(e)}")
        return None, None

if __name__ == '__main__':
    app, migrate = init_migrations()
    if app:
        print("Migrations initialized successfully")
    else:
        print("Failed to initialize migrations")
