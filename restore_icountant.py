"""
Script to restore iCountant system to last working state
"""
import logging
from datetime import datetime
from flask import current_app
from utils.backup_manager import DatabaseBackupManager
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def restore_system():
    """Restore system to last working state"""
    try:
        logger.info("Starting system restoration process...")
        
        # Initialize backup manager with database URL
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL environment variable not set")
            
        backup_manager = DatabaseBackupManager(database_url)
        
        # List available backups from today
        backups = backup_manager.list_backups()
        if not backups:
            logger.error("No backups found")
            return False
            
        # Filter today's backups
        today = datetime.now().strftime('%Y%m%d')
        todays_backups = [
            b for b in backups 
            if b['metadata']['timestamp'].startswith(today)
        ]
        
        if not todays_backups:
            logger.error("No backups found from today")
            return False
            
        # Sort backups by timestamp
        sorted_backups = sorted(
            todays_backups, 
            key=lambda x: x['metadata']['timestamp']
        )
        
        # Get the backup from early today (first backup of the day)
        early_backup = sorted_backups[0]
        backup_time = datetime.strptime(
            early_backup['metadata']['timestamp'],
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
