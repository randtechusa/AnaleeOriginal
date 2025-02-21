
import os
import sys
from flask import Flask
from flask_migrate import Migrate, upgrade
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import OperationalError
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_migrations():
    """Initialize database and run migrations"""
    try:
        from models import db
        from config import Config
        
        app = Flask(__name__)
        app.config.from_object(Config)
        
        db.init_app(app)
        migrate = Migrate(app, db)
        
        with app.app_context():
            try:
                # Ensure instance directory exists
                os.makedirs('instance', exist_ok=True)
                
                # Create database tables
                db.create_all()
                
                # Run migrations
                upgrade()
                
                logger.info("Database migrations completed successfully")
                return True
                
            except OperationalError as e:
                logger.error(f"Database operation failed: {e}")
                return False
                
            except Exception as e:
                logger.error(f"Migration error: {e}")
                return False
                
    except Exception as e:
        logger.error(f"Initialization error: {e}")
        return False

if __name__ == '__main__':
    success = init_migrations()
    sys.exit(0 if success else 1)
