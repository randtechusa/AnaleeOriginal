import os
import logging
from flask import Flask, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy.orm import DeclarativeBase

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask application
app = Flask(__name__)

# Configure Flask application
app.config.update(
    SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", "dev_key_123"),
    SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL").replace("postgres://", "postgresql://", 1) if os.environ.get("DATABASE_URL", "").startswith("postgres://") else os.environ.get("DATABASE_URL"),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SQLALCHEMY_ENGINE_OPTIONS={
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
)

# Initialize database
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
db.init_app(app)

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Initialize Flask-Login
@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

# Import routes after all configurations
with app.app_context():
    try:
        # Import models first
        from models import User, Account, Transaction
        
        # Verify database connection
        logger.info("Verifying database connection...")
        db.engine.connect()
        logger.info("Database connection successful")
        
        # Create database tables
        logger.info("Creating database tables...")
        db.create_all()
        logger.info("Database tables created successfully")
        
        # Import routes after models are ready
        logger.info("Initializing routes...")
        import routes
        logger.info("Routes initialized successfully")
        
    except Exception as e:
        logger.error(f"Error during initialization: {e}")
        logger.exception("Full stack trace:")
        raise
