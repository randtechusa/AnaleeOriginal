
import os
import sys
from flask import Flask
from flask_migrate import Migrate, upgrade
from models import db
from config import Config

def init_migrations():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    db.init_app(app)
    migrate = Migrate(app, db)
    
    with app.app_context():
        try:
            # Attempt to run migrations
            upgrade()
            print("Database migrations completed successfully")
            return True
        except Exception as e:
            print(f"Error initializing migrations: {e}")
            return False

if __name__ == '__main__':
    success = init_migrations()
    sys.exit(0 if success else 1)
