from flask import Flask
from flask_migrate import Migrate, upgrade
from models import db
from config import get_config

def run_migrations():
    """Run database migrations"""
    try:
        # Create Flask app with proper configuration
        app = Flask(__name__)
        app.config.from_object(get_config())
        
        # Initialize database and migrations
        db.init_app(app)
        migrate = Migrate(app, db)
        
        # Run migrations within application context
        with app.app_context():
            upgrade()
            
        print("Migrations completed successfully")
        return True
    except Exception as e:
        print(f"Error running migrations: {str(e)}")
        return False

if __name__ == '__main__':
    run_migrations()
