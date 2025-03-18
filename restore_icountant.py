"""
Script to restore iCountant system to last working state
"""
import logging
from datetime import datetime
from flask import current_app
from utils.backup_manager import DatabaseBackupManager
import os
import shutil
import sqlite3
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def restore_system():
    """Restore system to last working state"""
    try:
        logger.info("Starting system restoration process...")
        
        # Initialize backup manager with database URL
        database_url = os.environ.get('DATABASE_URL')
        
        # Enhanced detection - Check if we're using SQLite or PostgreSQL
        is_sqlite = False
        if not database_url or 'sqlite' in database_url.lower():
            is_sqlite = True
            logger.info("Using SQLite database for restoration")
            
            # Create a backup of the current SQLite database if it exists
            sqlite_path = os.path.join(os.getcwd(), 'instance', 'dev.db')
            if os.path.exists(sqlite_path):
                backup_time = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_dir = Path('backups')
                backup_dir.mkdir(exist_ok=True)
                
                backup_file = backup_dir / f"sqlite_backup_{backup_time}.db"
                try:
                    # Create a backup using SQLite's backup API
                    src = sqlite3.connect(sqlite_path)
                    dst = sqlite3.connect(str(backup_file))
                    src.backup(dst)
                    src.close()
                    dst.close()
                    
                    # Create metadata file for the backup
                    metadata = {
                        'timestamp': backup_time,
                        'database': 'sqlite',
                        'size': os.path.getsize(backup_file)
                    }
                    
                    metadata_file = backup_dir / f"backup_{backup_time}_metadata.json"
                    import json
                    with open(metadata_file, 'w') as f:
                        json.dump(metadata, f)
                    
                    logger.info(f"Created SQLite backup: {backup_file}")
                    return True
                except Exception as e:
                    logger.error(f"SQLite backup failed: {str(e)}")
                    return False
            else:
                logger.info("No SQLite database found to back up")
                return True
                
        else:
            # PostgreSQL backup process
            if not database_url:
                raise ValueError("DATABASE_URL environment variable not set")
                
            backup_manager = DatabaseBackupManager(database_url)
            
            # Create a backup first
            backup_result = backup_manager.create_backup()
            if backup_result:
                logger.info(f"Created new backup: {backup_result['file']}")
            
            # List available backups
            backups = backup_manager.list_backups()
            if not backups:
                logger.error("No backups found")
                return False
                
            # Sort backups by timestamp (newest first)
            sorted_backups = sorted(
                backups, 
                key=lambda x: x['metadata']['timestamp'],
                reverse=True
            )
            
            # Get the most recent backup
            latest_backup = sorted_backups[0]
            backup_time = datetime.strptime(
                latest_backup['metadata']['timestamp'],
                '%Y%m%d_%H%M%S'
            )
            
            logger.info(f"Found backup from {backup_time}")
            
            # Execute restoration
            success = backup_manager.restore_to_timestamp(backup_time)
            
            if success:
                logger.info("System successfully restored")
                return True
            else:
                logger.error("Restoration failed")
                return False
            
    except Exception as e:
        logger.error(f"Error during restoration: {str(e)}")
        return False

if __name__ == "__main__":
    restore_system()
