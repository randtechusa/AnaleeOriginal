import os
import logging
import sys
from datetime import datetime
from flask import Flask, current_app
from flask_migrate import Migrate
from dotenv import load_dotenv
from sqlalchemy import text
from flask_apscheduler import APScheduler
from models import db, login_manager, User, Account, Transaction, CompanySettings, UploadedFile, HistoricalData
from historical_data import historical_data as historical_data_blueprint

# Configure logging with more detailed error reporting
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log')
    ]
)

# Create module logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Load environment variables
load_dotenv()

# Initialize Flask extensions
migrate = Migrate()
scheduler = APScheduler()

def verify_database():
    """Verify database connection and check required tables"""
    try:
        logger.info("Verifying database connection...")
        with db.engine.connect() as conn:
            # Test basic connection
            conn.execute(text('SELECT 1'))
            logger.info("Basic database connection successful")
            
            # List existing tables
            tables_query = text("""
                SELECT tablename 
                FROM pg_catalog.pg_tables 
                WHERE schemaname != 'pg_catalog' 
                AND schemaname != 'information_schema';
            """)
            existing_tables = [row[0] for row in conn.execute(tables_query)]
            logger.info(f"Existing tables: {existing_tables}")
            
            # Create tables if they don't exist
            try:
                db.create_all()
                logger.info("Database tables created/verified successfully")
                
                # Verify each model's table exists
                for table in db.metadata.tables:
                    if table not in existing_tables:
                        logger.warning(f"Table {table} may not have been created properly")
                    else:
                        logger.info(f"Table {table} verified")
                return True
                
            except Exception as table_error:
                logger.error(f"Error creating tables: {str(table_error)}")
                logger.exception("Full table creation error stacktrace:")
                return False
            
    except Exception as db_error:
        logger.error(f"Database connection failed: {str(db_error)}")
        logger.exception("Full database connection error stacktrace:")
        return False

def create_app(env=os.environ.get('FLASK_ENV', 'production')):
    """Create and configure the Flask application"""
    try:
        # Initialize Flask application
        app = Flask(__name__)

        # Load the appropriate configuration
        app.config.from_object(f'config.{env.capitalize()}Config')

        # Get appropriate database URL based on environment
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            logger.error("Database URL is not set")
            return None

        # Handle legacy database URL format
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)

        # Configure Flask app
        config = {
            'SECRET_KEY': os.environ.get("FLASK_SECRET_KEY", os.urandom(24).hex()),
            'SQLALCHEMY_DATABASE_URI': database_url,
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
            'TEMPLATES_AUTO_RELOAD': True,
            'SQLALCHEMY_ENGINE_OPTIONS': {
                'pool_pre_ping': True,
                'pool_size': 5,
                'pool_timeout': 30,
                'pool_recycle': 300,
                'max_overflow': 2
            }
        }

        app.config.update(config)
        logger.debug("Flask app configuration completed")

        # Initialize Flask extensions
        db.init_app(app)
        migrate.init_app(app, db)
        login_manager.init_app(app)
        login_manager.login_view = 'main.login'

        # Initialize scheduler
        scheduler.init_app(app)
        scheduler.start()

        with app.app_context():
            # Verify database connection
            try:
                db.session.execute(text('SELECT 1'))
                logger.info("Database connection verified")
            except Exception as db_error:
                logger.error(f"Database connection failed: {str(db_error)}")
                return None

            # Create database tables
            try:
                db.create_all()
                logger.info("Database tables created successfully")
            except Exception as table_error:
                logger.error(f"Failed to create database tables: {str(table_error)}")
                return None

            # Register blueprints
            try:
                from routes import main as main_blueprint
                app.register_blueprint(main_blueprint)

                from reports import reports as reports_blueprint
                app.register_blueprint(reports_blueprint, url_prefix='/reports')

                # Register historical data blueprint
                app.register_blueprint(historical_data_blueprint)

                logger.info("Blueprints registered successfully")
            except Exception as blueprint_error:
                logger.error(f"Error registering blueprints: {str(blueprint_error)}")
                raise

            logger.info("Application initialization completed successfully")
            return app

    except Exception as e:
        logger.error(f"Critical error in application creation: {str(e)}")
        return None

if __name__ == '__main__':
    try:
        # Initialize the application
        logger.info("Starting application initialization...")
        app = create_app()
        
        if not app:
            logger.error("Application creation failed")
            sys.exit(1)
            
        # Get port and configure server
        port = 5000  # Force port 5000 for Replit
        logger.info(f"Configuring server to run on port {port}")
        
        # Verify database connection before starting
        with app.app_context():
            if not verify_database():
                logger.error("Database verification failed")
                sys.exit(1)
                
            # Ensure all tables exist
            try:
                db.create_all()
                logger.info("Database tables verified/created")
            except Exception as db_error:
                logger.error(f"Error creating database tables: {str(db_error)}")
                sys.exit(1)
            
        # Start the server
        logger.info(f"Starting Flask application on http://0.0.0.0:{port}")
        app.run(
            host='0.0.0.0',
            port=port,
            debug=True,  # Enable debug mode
            use_reloader=False  # Disable reloader to prevent duplicate processes
        )
    except Exception as e:
        logger.error(f"Critical error starting application: {str(e)}")
        logger.exception("Full stack trace:")
        sys.exit(1)