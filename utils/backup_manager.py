import logging
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from flask_apscheduler import APScheduler
from sqlalchemy import create_engine, text
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseBackupManager:
    """Manages database backups and restorations"""
    
    def __init__(self, database_url: str):
        """Initialize the backup manager with database configuration"""
        self.database_url = database_url
        self.backup_dir = Path('backups')
        self.backup_dir.mkdir(exist_ok=True)
        
        # Parse database URL for pg_dump/pg_restore
        try:
            self.db_info = self._parse_database_url(database_url)
            logger.info(f"Initialized backup manager for database: {self.db_info['database']}")
        except Exception as e:
            logger.error(f"Failed to parse database URL: {str(e)}")
            raise
    
    def _parse_database_url(self, url: str) -> Dict[str, str]:
        """Parse database URL into components"""
        try:
            engine = create_engine(url)
            return {
                'host': engine.url.host,
                'port': engine.url.port or 5432,
                'user': engine.url.username,
                'password': engine.url.password,
                'database': engine.url.database
            }
        except Exception as e:
            logger.error(f"Database URL parsing failed: {str(e)}")
            raise
    
    def create_backup(self) -> Optional[Dict[str, Any]]:
        """Create a new database backup"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = self.backup_dir / f"backup_{timestamp}.sql"
            
            # Prepare pg_dump command
            cmd = [
                'pg_dump',
                '--clean',
                '--if-exists',
                f"--host={self.db_info['host']}",
                f"--port={self.db_info['port']}",
                f"--username={self.db_info['user']}",
                f"--dbname={self.db_info['database']}",
                '--format=c',
                '--file', str(backup_file)
            ]
            
            # Set environment for authentication
            env = os.environ.copy()
            env['PGPASSWORD'] = self.db_info['password']
            
            # Execute backup
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                # Create metadata file
                metadata = {
                    'timestamp': timestamp,
                    'database': self.db_info['database'],
                    'size': os.path.getsize(backup_file)
                }
                
                metadata_file = self.backup_dir / f"backup_{timestamp}_metadata.json"
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f)
                
                logger.info(f"Backup created successfully: {backup_file}")
                return {
                    'file': str(backup_file),
                    'metadata': metadata
                }
            else:
                logger.error(f"Backup failed: {result.stderr}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating backup: {str(e)}")
            return None
    
    def restore_to_timestamp(self, target_timestamp: datetime) -> bool:
        """
        Restore database to the closest backup before the target timestamp
        
        Args:
            target_timestamp: Target datetime to restore to
            
        Returns:
            bool: True if restoration was successful
        """
        try:
            # Find closest backup before target timestamp
            backup = self._find_closest_backup(target_timestamp)
            if not backup:
                logger.error("No suitable backup found for restoration")
                return False
            
            backup_file = Path(backup['file'])
            if not backup_file.exists():
                logger.error(f"Backup file not found: {backup_file}")
                return False
            
            # Prepare pg_restore command
            cmd = [
                'pg_restore',
                '--clean',
                '--if-exists',
                f"--host={self.db_info['host']}",
                f"--port={self.db_info['port']}",
                f"--username={self.db_info['user']}",
                f"--dbname={self.db_info['database']}",
                str(backup_file)
            ]
            
            env = os.environ.copy()
            env['PGPASSWORD'] = self.db_info['password']
            
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"Successfully restored to backup from {backup['metadata']['timestamp']}")
                return True
            else:
                logger.error(f"Restore failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error during restoration: {str(e)}")
            return False
    
    def _find_closest_backup(self, target_timestamp: datetime) -> Optional[Dict[str, Any]]:
        """Find the closest backup before the target timestamp"""
        try:
            backups = self.list_backups()
            if not backups:
                return None
            
            closest_backup = None
            smallest_diff = timedelta.max
            
            for backup in backups:
                backup_time = datetime.strptime(
                    backup['metadata']['timestamp'],
                    '%Y%m%d_%H%M%S'
                )
                
                if backup_time <= target_timestamp:
                    diff = target_timestamp - backup_time
                    if diff < smallest_diff:
                        smallest_diff = diff
                        closest_backup = backup
            
            return closest_backup
            
        except Exception as e:
            logger.error(f"Error finding closest backup: {str(e)}")
            return None
    
    def restore_to_days_ago(self, days: int, target_minute: int = 59, target_hour: int = 23) -> bool:
        """
        Restore to a specific minute of a day N days ago
        
        Args:
            days: Number of days to go back
            target_minute: Minute of the hour (0-59)
            target_hour: Hour of the day (0-23)
        """
        try:
            current_time = datetime.now()
            target_date = current_time - timedelta(days=days)
            target_timestamp = target_date.replace(
                hour=target_hour,
                minute=target_minute,
                second=59,
                microsecond=999999
            )
            
            logger.info(f"Attempting to restore to {target_timestamp}")
            return self.restore_to_timestamp(target_timestamp)
            
        except Exception as e:
            logger.error(f"Error during days-ago restoration: {str(e)}")
            return False
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups with their metadata"""
        try:
            backups = []
            for metadata_file in self.backup_dir.glob('*_metadata.json'):
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                
                backup_file = self.backup_dir / f"backup_{metadata['timestamp']}.sql"
                if backup_file.exists():
                    backups.append({
                        'file': str(backup_file),
                        'metadata': metadata
                    })
            
            return sorted(backups, key=lambda x: x['metadata']['timestamp'])
            
        except Exception as e:
            logger.error(f"Error listing backups: {str(e)}")
            return []

    def cleanup_old_backups(self, keep_days=7):
        """Remove backups older than specified days"""
        try:
            cutoff_date = datetime.now().timestamp() - (keep_days * 24 * 60 * 60)
            for backup in self.list_backups():
                backup_time = datetime.strptime(
                    backup['metadata']['timestamp'],
                    '%Y%m%d_%H%M%S'
                ).timestamp()
                
                if backup_time < cutoff_date:
                    backup_file = Path(backup['file'])
                    metadata_file = self.backup_dir / f"{backup_file.stem}_metadata.json"
                    
                    if backup_file.exists():
                        backup_file.unlink()
                    if metadata_file.exists():
                        metadata_file.unlink()
                        
                    logger.info(f"Removed old backup: {backup_file}")
                    
        except Exception as e:
            logger.error(f"Error cleaning up old backups: {str(e)}")

def init_backup_scheduler(app):
    """Initialize the backup scheduler"""
    scheduler = APScheduler()
    
    # Configure scheduler
    app.config['SCHEDULER_API_ENABLED'] = True
    app.config['SCHEDULER_EXECUTORS'] = {
        'default': {'type': 'threadpool', 'max_workers': 5}
    }
    
    scheduler.init_app(app)
    
    # Create backup manager instance
    backup_manager = DatabaseBackupManager(app.config['SQLALCHEMY_DATABASE_URI'])
    
    # Add jobs
    scheduler.add_job(
        id='daily_backup',
        func=backup_manager.create_backup,
        trigger='cron',
        hour=0,  # Run at midnight
        minute=0
    )
    
    scheduler.add_job(
        id='backup_cleanup',
        func=backup_manager.cleanup_old_backups,
        trigger='cron',
        hour=1,  # Run at 1 AM
        minute=0
    )
    
    scheduler.start()
    logger.info("Backup scheduler initialized")
    return scheduler
