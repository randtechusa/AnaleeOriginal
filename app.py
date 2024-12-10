import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask application
app = Flask(__name__)

# Configure Flask application
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise ValueError("DATABASE_URL environment variable is not set")

if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

logger.info("Configuring Flask application with database URL")
app.config.update(
    SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", os.urandom(24).hex()),
    SQLALCHEMY_DATABASE_URI=database_url,
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SQLALCHEMY_ENGINE_OPTIONS={
        "pool_recycle": 300,
        "pool_pre_ping": True,
        "connect_args": {
            "connect_timeout": 10
        }
    }
)

# Initialize Flask extensions
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

logger.info(f"Database URL configured (masked): {database_url.split('@')[0]}@****")

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

try:
    with app.app_context():
        # Import models and routes after db initialization
        import models
        import routes
        
        # Create database tables
        logger.info("Creating database tables...")
        db.create_all()
        
        logger.info("Application initialization completed successfully")
except Exception as e:
    logger.error(f"Error during initialization: {e}")
    logger.exception("Full stack trace:")
    raise
