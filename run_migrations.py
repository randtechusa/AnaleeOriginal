
import os
import sys
import time
import argparse
from flask import Flask
from flask_migrate import Migrate, upgrade
from sqlalchemy.exc import OperationalError, SQLAlchemyError
import logging

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
        from models import db
        from config import Config, DevelopmentConfig
        
        app = Flask(__name__)
        
        # Try to use the environment-specific config, fall back to development if not found
        config_name = os.environ.get('FLASK_ENV', 'development')
        if config_name == 'development':
            app.config.from_object(DevelopmentConfig)
        else:
            app.config.from_object(Config)
        
        # Override database URI from env if available
        if os.environ.get('DATABASE_URL'):
            app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
        
        logger.info(f"Using database: {app.config['SQLALCHEMY_DATABASE_URI']}")
        
        db.init_app(app)
        migrate = Migrate(app, db)
        
        with app.app_context():
            for attempt in range(retry_count):
                try:
                    # Ensure instance directory exists
                    os.makedirs('instance', exist_ok=True)
                    
                    # Attempt to connect to the database
                    db.engine.connect()
                    logger.info("Database connection successful")
                    
                    # Create database tables
                    db.create_all()
                    logger.info("Tables created successfully")
                    
                    # Run migrations
                    logger.info("Starting database migrations...")
                    upgrade()
                    
                    logger.info("Database migrations completed successfully")
                    return True
                    
                except OperationalError as e:
                    if 'endpoint is disabled' in str(e):
                        logger.warning("PostgreSQL endpoint is disabled, may need to be woken up")
                        # Fall back to SQLite if needed
                        if attempt == retry_count - 1:
                            logger.warning("Falling back to SQLite database")
                            app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/dev.db'
                            db.init_app(app)
                            continue
                    
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
