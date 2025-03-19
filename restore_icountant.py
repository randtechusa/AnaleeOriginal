"""
Script to restore iCountant system to last working state
"""
import logging
from datetime import datetime
import os
import shutil
import sqlite3
import json
from pathlib import Path
from utils.backup_manager import DatabaseBackupManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def restore_system():
    """Restore system to last working state"""
    try:
        logger.info("Starting system restoration process...")
        
        # Get the database URL from the environment
        database_url = os.environ.get('DATABASE_URL')
        
        # Create backup directories
        backup_dir = Path('backups')
        backup_dir.mkdir(exist_ok=True)
        
        # Generate a backup timestamp
        backup_time = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # First try to handle SQLite database (which is our fallback)
        sqlite_path = os.path.join(os.getcwd(), 'instance', 'dev.db')
        if os.path.exists(sqlite_path):
            logger.info("Found SQLite database - creating backup")
            
            # Create a SQLite backup
            sqlite_backup_file = backup_dir / f"sqlite_backup_{backup_time}.db"
            try:
                # Create a backup using SQLite's backup API
                src = sqlite3.connect(sqlite_path)
                dst = sqlite3.connect(str(sqlite_backup_file))
                src.backup(dst)
                src.close()
                dst.close()
                
                # Create metadata file for the backup
                metadata = {
                    'timestamp': backup_time,
                    'database': 'sqlite',
                    'size': os.path.getsize(sqlite_backup_file),
                    'path': str(sqlite_backup_file)
                }
                
                metadata_file = backup_dir / f"backup_{backup_time}_metadata.json"
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f)
                
                logger.info(f"Created SQLite backup: {sqlite_backup_file}")
            except Exception as e:
                logger.error(f"SQLite backup failed: {str(e)}")
        else:
            logger.info("No SQLite database found to back up")
        
        # Try PostgreSQL backup if we have a database URL that's not SQLite
        if database_url and 'sqlite' not in database_url.lower():
            logger.info("Attempting PostgreSQL backup")
            try:
                # First check if the PostgreSQL endpoint is available
                from sqlalchemy import create_engine, text
                from sqlalchemy.exc import OperationalError

                # Create a minimal connection to test the endpoint
                try:
                    engine = create_engine(database_url, connect_args={'connect_timeout': 10})
                    with engine.connect() as conn:
                        conn.execute(text('SELECT 1'))
                    postgresql_available = True
                    logger.info("PostgreSQL endpoint is available, proceeding with backup")
                except OperationalError as e:
                    error_str = str(e).lower()
                    if 'endpoint is disabled' in error_str:
                        logger.warning("PostgreSQL endpoint is disabled, cannot create backup")
                        postgresql_available = False
                    else:
                        # Some other operational error
                        logger.error(f"PostgreSQL connection error: {e}")
                        postgresql_available = False
                except Exception as e:
                    logger.error(f"Error testing PostgreSQL connection: {e}")
                    postgresql_available = False
                
                # Only attempt backup if PostgreSQL is available
                if postgresql_available:
                    backup_manager = DatabaseBackupManager(database_url)
                    
                    # Create a backup
                    backup_result = backup_manager.create_backup()
                    if backup_result:
                        logger.info(f"Created new PostgreSQL backup: {backup_result['file']}")
                    else:
                        logger.warning("PostgreSQL backup creation failed")
                else:
                    logger.warning("Skipping PostgreSQL backup due to connection issues")
            except Exception as e:
                logger.error(f"PostgreSQL backup error: {str(e)}")

        # List all available backups (both SQLite and PostgreSQL)
        all_backups = []
        
        # Find all metadata files and read them
        for metadata_file in backup_dir.glob('*_metadata.json'):
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                
                # Check if the corresponding backup file exists
                if metadata.get('database') == 'sqlite':
                    backup_file = backup_dir / f"sqlite_backup_{metadata['timestamp']}.db"
                    # Also check the alternative path format if provided in metadata
                    if not backup_file.exists() and 'path' in metadata:
                        backup_file = Path(metadata['path'])
                else:
                    backup_file = backup_dir / f"backup_{metadata['timestamp']}.sql"
                    
                if backup_file.exists():
                    all_backups.append({
                        'file': str(backup_file),
                        'metadata': metadata
                    })
            except Exception as e:
                logger.error(f"Error reading backup metadata {metadata_file}: {str(e)}")
        
        # If no backups were found, we can't restore
        if not all_backups:
            logger.error("No valid backups found for restoration")
            return False
        
        # Sort backups by timestamp (newest first)
        sorted_backups = sorted(
            all_backups, 
            key=lambda x: x['metadata']['timestamp'],
            reverse=True
        )
        
        # Get the most recent backup
        latest_backup = sorted_backups[0]
        backup_timestamp = latest_backup['metadata']['timestamp']
        backup_type = latest_backup['metadata'].get('database', 'postgresql')
        
        logger.info(f"Found backup from {backup_timestamp} (type: {backup_type})")
        
        # Perform the restoration based on backup type
        if backup_type == 'sqlite':
            # SQLite restoration
            backup_file = Path(latest_backup['file'])
            
            # Make sure the instance directory exists
            instance_dir = Path('instance')
            instance_dir.mkdir(exist_ok=True)
            
            # Restore the SQLite database
            try:
                # Close any open database connections
                import gc
                gc.collect()
                
                # Simple file copy for SQLite
                shutil.copy2(backup_file, sqlite_path)
                logger.info(f"Successfully restored SQLite database from {backup_file}")
                return True
            except Exception as e:
                logger.error(f"SQLite restoration failed: {str(e)}")
                return False
        else:
            # PostgreSQL restoration
            if not database_url:
                logger.error("Cannot restore PostgreSQL backup - DATABASE_URL not set")
                logger.info("Checking for SQLite backups instead")
                # Since we can't restore PostgreSQL, try SQLite backups directly
                sqlite_backups = [b for b in sorted_backups if b['metadata'].get('database') == 'sqlite']
                if sqlite_backups:
                    # Override with latest SQLite backup
                    latest_backup = sqlite_backups[0]
                    backup_timestamp = latest_backup['metadata']['timestamp']
                    logger.info(f"Found SQLite backup from {backup_timestamp}, using this instead")
                    
                    # Restore SQLite backup
                    backup_file = Path(latest_backup['file'])
                    
                    # Make sure the instance directory exists
                    instance_dir = Path('instance')
                    instance_dir.mkdir(exist_ok=True)
                    
                    # Restore the SQLite database
                    try:
                        import gc
                        gc.collect()
                        
                        # Copy the SQLite backup file to the instance directory
                        shutil.copy2(backup_file, sqlite_path)
                        logger.info(f"Successfully restored SQLite database from {backup_file}")
                        return True
                    except Exception as e:
                        logger.error(f"SQLite restoration failed: {str(e)}")
                        return False
                else:
                    logger.error("No SQLite backups found as fallback")
                    return False
                
            # Check if PostgreSQL endpoint is available
            from sqlalchemy import create_engine, text
            from sqlalchemy.exc import OperationalError

            # Create a minimal connection to test the endpoint
            postgresql_available = False
            try:
                engine = create_engine(database_url, connect_args={'connect_timeout': 10})
                with engine.connect() as conn:
                    conn.execute(text('SELECT 1'))
                postgresql_available = True
                logger.info("PostgreSQL endpoint is available, proceeding with restoration")
            except OperationalError as e:
                error_str = str(e).lower()
                if 'endpoint is disabled' in error_str:
                    logger.warning("PostgreSQL endpoint is disabled, cannot perform restoration")
                    postgresql_available = False
                else:
                    # Some other operational error
                    logger.error(f"PostgreSQL connection error: {e}")
                    postgresql_available = False
            except Exception as e:
                logger.error(f"Error testing PostgreSQL connection: {e}")
                postgresql_available = False
                
            # If PostgreSQL is not available, fall back to SQLite if we have SQLite backups
            if not postgresql_available:
                logger.warning("PostgreSQL endpoint unavailable, checking for SQLite backups")
                sqlite_backups = [b for b in sorted_backups if b['metadata'].get('database') == 'sqlite']
                if sqlite_backups:
                    # Override with latest SQLite backup
                    latest_backup = sqlite_backups[0]
                    backup_timestamp = latest_backup['metadata']['timestamp']
                    logger.info(f"Found SQLite backup from {backup_timestamp}, using this instead")
                    
                    # Restore SQLite backup
                    backup_file = Path(latest_backup['file'])
                    
                    # Make sure the instance directory exists
                    instance_dir = Path('instance')
                    instance_dir.mkdir(exist_ok=True)
                    
                    # Restore the SQLite database
                    try:
                        import gc
                        gc.collect()
                        
                        # Copy the SQLite backup file to the instance directory
                        shutil.copy2(backup_file, sqlite_path)
                        logger.info(f"Successfully restored SQLite database from {backup_file}")
                        return True
                    except Exception as e:
                        logger.error(f"SQLite restoration failed: {str(e)}")
                        return False
                else:
                    logger.error("No SQLite backups found as fallback")
                    return False
                
            # Proceed with PostgreSQL restoration
            try:
                backup_manager = DatabaseBackupManager(database_url)
                backup_time = datetime.strptime(backup_timestamp, '%Y%m%d_%H%M%S')
                
                # Execute restoration
                success = backup_manager.restore_to_timestamp(backup_time)
                
                if success:
                    logger.info("PostgreSQL database successfully restored")
                    return True
                else:
                    logger.error("PostgreSQL restoration failed")
                    
                    # If PostgreSQL restore failed but we have SQLite backups, try those
                    sqlite_backups = [b for b in sorted_backups if b['metadata'].get('database') == 'sqlite']
                    if sqlite_backups:
                        logger.info("Falling back to SQLite backup restoration")
                        # Get the most recent SQLite backup
                        sqlite_backup = sqlite_backups[0]
                        backup_file = Path(sqlite_backup['file'])
                        
                        # Make sure the instance directory exists
                        instance_dir = Path('instance')
                        instance_dir.mkdir(exist_ok=True)
                        
                        # Restore the SQLite database
                        try:
                            import gc
                            gc.collect()
                            
                            # Copy the SQLite backup file to the instance directory
                            shutil.copy2(backup_file, sqlite_path)
                            logger.info(f"Successfully restored SQLite database from {backup_file}")
                            return True
                        except Exception as e:
                            logger.error(f"SQLite restoration failed: {str(e)}")
                            return False
                    return False
            except Exception as e:
                logger.error(f"Error during PostgreSQL restoration: {str(e)}")
                
                # Try SQLite backups as a last resort
                sqlite_backups = [b for b in sorted_backups if b['metadata'].get('database') == 'sqlite']
                if sqlite_backups:
                    logger.info("Error with PostgreSQL, falling back to SQLite backup restoration")
                    # Get the most recent SQLite backup
                    sqlite_backup = sqlite_backups[0]
                    backup_file = Path(sqlite_backup['file'])
                    
                    # Restore the SQLite database
                    try:
                        import gc
                        gc.collect()
                        
                        # Copy the SQLite backup file to the instance directory
                        shutil.copy2(backup_file, sqlite_path)
                        logger.info(f"Successfully restored SQLite database from {backup_file}")
                        return True
                    except Exception as e_sqlite:
                        logger.error(f"SQLite restoration failed: {str(e_sqlite)}")
                        return False
                return False
            
    except Exception as e:
        logger.error(f"Error during restoration: {str(e)}")
        return False

if __name__ == "__main__":
    restore_system()
