import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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
db = SQLAlchemy()
login_manager = LoginManager()

def init_app():
    """Initialize the Flask application"""
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    
    with app.app_context():
        try:
            # Import models and create tables
            from models import User, Account, Transaction
            logger.info("Creating database tables...")
            db.create_all()
            logger.info("Database tables created successfully")
            
            # Register blueprints
            from routes import main as main_blueprint
            app.register_blueprint(main_blueprint)
            logger.info("Routes initialized successfully")
            
        except Exception as e:
            logger.error(f"Error during initialization: {str(e)}")
            logger.exception("Full stack trace:")
            raise
    
    return app

@login_manager.user_loader
def load_user(user_id):
    from models import User
    try:
        return User.query.get(int(user_id))
    except Exception as e:
        logger.error(f"Error loading user {user_id}: {str(e)}")
        return None

# Initialize the application
app = init_app()
