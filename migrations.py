from flask_migrate import Migrate
from models import db
from app import create_app

def init_migrations():
    """Initialize database migrations"""
    try:
        app = create_app()
        migrate = Migrate(app, db)
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