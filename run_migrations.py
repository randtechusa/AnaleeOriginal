
import os
import sys
import time
import argparse
from flask import Flask
from flask_migrate import Migrate, upgrade
from sqlalchemy.exc import OperationalError, SQLAlchemyError
import logging
import importlib

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def init_migrations(retry_count=3, retry_delay=5):
    """
    Initialize database and run migrations with retry capability
    
    Args:
        retry_count: Number of times to retry on failure
        retry_delay: Seconds to wait between retries
    """
    try:
        # Create a Flask app for migration
        app = Flask(__name__)
        
        # Configure the app using the config module
        try:
            from config import Config
            app.config.from_object(Config)
        except ImportError as e:
            logger.error(f"Failed to import configuration: {e}")
            return False
        
        # Override database URI from env if available
        if os.environ.get('DATABASE_URL'):
            app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
        
        # Import db from extensions to ensure we use the same SQLAlchemy instance
        from extensions import db, migrate
        
        # Initialize db with this app
        db.init_app(app)
        
        # Initialize migrations with this app and db (no need to create a new Migrate instance)
        migrate.init_app(app, db)
        
        with app.app_context():
            for attempt in range(retry_count):
                try:
                    # Ensure instance directory exists
                    os.makedirs('instance', exist_ok=True)
                    
                    # Get the current database URI
                    current_db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
                    logger.info(f"Using database: {current_db_uri}")
                    
                    # Attempt to connect to the database with better error handling
                    conn = db.engine.connect()
                    result = conn.execute("SELECT 1")
                    conn.close()
                    logger.info("Database connection and query test successful")
                    
                    # Run migrations
                    logger.info("Starting database migrations...")
                    upgrade()
                    
                    logger.info("Database migrations completed successfully")
                    return True
                    
                except OperationalError as e:
                    error_str = str(e).lower()
                    if 'endpoint is disabled' in error_str:
                        logger.warning("PostgreSQL endpoint is disabled, may need to be woken up")
                        
                        # Try to wake up the endpoint using the wake_up_endpoint method from db_health
                        current_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
                        if current_uri and 'sqlite' not in current_uri.lower() and attempt < retry_count - 1:
                            try:
                                from utils.db_health import DatabaseHealth
                                db_health = DatabaseHealth.get_instance()
                                wake_result = db_health.wake_up_endpoint(current_uri)
                                if wake_result:
                                    logger.info("Successfully woke up the database endpoint")
                                    continue
                            except Exception as we:
                                logger.error(f"Error trying to wake up endpoint: {we}")
                        
                        # Fall back to SQLite if this is our last attempt
                        current_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
                        if attempt == retry_count - 1 and current_uri and 'sqlite' not in current_uri.lower():
                            logger.warning("Falling back to SQLite database for migrations")
                            app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/dev.db'
                            # Dispose existing connections and reconnect
                            db.engine.dispose()
                            
                            # Create tables directly for SQLite - no need for migrations
                            logger.info("Creating tables directly for SQLite database")
                            try:
                                app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/dev.db'
                                
                                # Dispose of old engine and create a new one for SQLite
                                db.engine.dispose()
                                
                                # Instead of reinitializing, create new SQLAlchemy instance for migration purposes only
                                from sqlalchemy import create_engine
                                from sqlalchemy.orm import scoped_session, sessionmaker
                                from models import get_base
                                
                                # Get the Base with the current model definitions
                                Base = get_base()
                                
                                # Create a new engine for SQLite with better configuration
                                engine = create_engine('sqlite:///instance/dev.db', 
                                                      connect_args={'check_same_thread': False},
                                                      pool_recycle=1800)
                                
                                # Drop existing tables if they exist to avoid conflicts
                                try:
                                    # Check if we need to drop existing tables
                                    conn = engine.connect()
                                    result = conn.execute(sql_text("SELECT name FROM sqlite_master WHERE type='table'"))
                                    tables = [row[0] for row in result]
                                    conn.close()
                                    
                                    if tables:
                                        logger.info(f"Found existing tables: {', '.join(tables)}")
                                        logger.info("Dropping existing tables to ensure clean state")
                                        Base.metadata.drop_all(engine)
                                except Exception as e:
                                    logger.warning(f"Error checking existing tables: {e}")
                                
                                # Create all tables directly from the models
                                Base.metadata.create_all(engine)
                                logger.info("Created all database tables from models")
                                
                                # Import text for SQL execution early to avoid reference errors
                                from sqlalchemy import text as sql_text
                                
                                # Create a test session to verify it works
                                session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
                                session.execute(sql_text('SELECT 1'))
                                session.commit()
                                session.remove()
                                    
                                logger.info("SQLite tables created successfully")
                                return True  # Exit the function with success
                            except Exception as e:
                                logger.error(f"Failed to create SQLite tables: {e}")
                                return False  # Exit with failure
                    
                    logger.error(f"Database operation failed (attempt {attempt+1}/{retry_count}): {e}")
                    if attempt < retry_count - 1:
                        logger.info(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                    else:
                        return False
                    
                except SQLAlchemyError as e:
                    logger.error(f"SQLAlchemy error (attempt {attempt+1}/{retry_count}): {e}")
                    if attempt < retry_count - 1:
                        logger.info(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                    else:
                        return False
                    
                except Exception as e:
                    logger.error(f"Migration error (attempt {attempt+1}/{retry_count}): {e}")
                    logger.error(f"Error details: {type(e).__name__}: {str(e)}")
                    if attempt < retry_count - 1:
                        logger.info(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                    else:
                        return False
                
    except Exception as e:
        logger.error(f"Initialization error: {e}")
        return False

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run database migrations')
    parser.add_argument('--retry-count', type=int, default=3, help='Number of times to retry on failure')
    parser.add_argument('--retry-delay', type=int, default=5, help='Seconds to wait between retries')
    args = parser.parse_args()
    
    logger.info(f"Starting migration with retry count: {args.retry_count}, retry delay: {args.retry_delay}s")
    success = init_migrations(args.retry_count, args.retry_delay)
    
    if success:
        logger.info("Migration completed successfully")
        sys.exit(0)
    else:
        logger.error("Migration failed after multiple attempts")
        sys.exit(1)
