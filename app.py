import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from flask_login import LoginManager
from flask_migrate import Migrate
from dotenv import load_dotenv
import os
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask extensions
from models import db, login_manager
migrate = Migrate()

def create_app():
    """Create and configure the Flask application"""
    try:
        logger.info("Starting Flask application creation...")
        app = Flask(__name__)
        
        # Configure Flask application
        logger.debug("Checking for DATABASE_URL...")
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            logger.error("DATABASE_URL environment variable is not set")
            raise ValueError("DATABASE_URL environment variable is not set")

        if database_url.startswith("postgres://"):
            logger.debug("Converting postgres:// to postgresql:// in DATABASE_URL")
            database_url = database_url.replace("postgres://", "postgresql://", 1)

        logger.info("Configuring Flask application settings...")
        secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24).hex())
        logger.debug("Generated/retrieved secret key")
        
        app.config.update(
            SECRET_KEY=secret_key,
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
        logger.info("Flask application configuration complete")
        
        # Initialize Flask extensions with app
        logger.debug("Initializing Flask extensions...")
        db.init_app(app)
        migrate.init_app(app, db)
        login_manager.init_app(app)
        login_manager.login_view = 'main.login'
        
        return app
        
    except Exception as e:
        logger.error(f"Failed to create Flask application: {str(e)}")
        logger.exception("Full stack trace:")
        raise
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'
    
    with app.app_context():
        try:
            # Import models
            from models import User, Account, Transaction, UploadedFile, CompanySettings
            
            # Register blueprints
            from routes import main as main_blueprint
            app.register_blueprint(main_blueprint)
            
            # Initialize database if needed
            try:
                logger.info("Beginning database initialization...")
                
                # Test database connection first
                logger.debug("Testing database connection...")
                with db.engine.connect() as conn:
                    result = conn.execute(text("SELECT 1"))
                    if result.scalar() == 1:
                        logger.info("Database connection successful")
                    else:
                        raise Exception("Database connection test failed")
                
                logger.info("Creating database tables...")
                db.create_all()
                logger.info("Database tables created successfully")
                
                # Verify tables were created
                logger.debug("Verifying database tables...")
                with db.engine.connect() as conn:
                    tables = conn.execute(text("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public'"))
                    table_list = [table[0] for table in tables]
                    logger.info(f"Available tables: {table_list}")
                    
                    # Verify essential tables exist
                    required_tables = {'users', 'transactions', 'account', 'company_settings'}
                    missing_tables = required_tables - set(table_list)
                    if missing_tables:
                        logger.error(f"Missing required tables: {missing_tables}")
                        raise Exception(f"Database initialization incomplete - missing tables: {missing_tables}")
                    
                logger.info("Database initialization completed successfully")
                
            except Exception as db_error:
                logger.error(f"Database initialization error: {str(db_error)}")
                logger.exception("Full stack trace:")
                raise
                
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

# Initialize the application (only if running directly)
if __name__ == '__main__':
    app = create_app()
