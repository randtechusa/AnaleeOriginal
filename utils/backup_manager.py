import logging
import os
import subprocess
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from flask_apscheduler import APScheduler
from sqlalchemy import create_engine, text

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
            
            # Check if this is a SQLite URL
            if 'sqlite' in url.lower():
                return {
                    'database': 'sqlite',
                    'path': engine.url.database
                }
            
            # For PostgreSQL and other database types
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
            
            # Check if this is SQLite or PostgreSQL
            if 'database' in self.db_info and self.db_info['database'] == 'sqlite':
                # Handle SQLite backup
                sqlite_path = self.db_info.get('path')
                if not sqlite_path:
                    logger.error("SQLite path not found in database info")
                    return None
                
                # For SQLite, use the .db extension
                backup_file = self.backup_dir / f"backup_{timestamp}.db"
                
                # Use SQLite's built-in backup functionality
                try:
                    # Connect to source database
                    src_conn = sqlite3.connect(sqlite_path)
                    # Connect to destination (backup) database
                    dst_conn = sqlite3.connect(str(backup_file))
                    # Perform backup
                    src_conn.backup(dst_conn)
                    # Close connections
                    src_conn.close()
                    dst_conn.close()
                    
                    # Create metadata
                    metadata = {
                        'timestamp': timestamp,
                        'database': 'sqlite',
                        'path': sqlite_path,
                        'size': os.path.getsize(backup_file)
                    }
                    
                    metadata_file = self.backup_dir / f"backup_{timestamp}_metadata.json"
                    with open(metadata_file, 'w') as f:
                        json.dump(metadata, f)
                    
                    logger.info(f"SQLite backup created successfully: {backup_file}")
                    return {
                        'file': str(backup_file),
                        'metadata': metadata
                    }
                    
                except Exception as e:
                    logger.error(f"SQLite backup failed: {str(e)}")
                    return None
            
            else:
                # Handle PostgreSQL backup
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
                    
                    logger.info(f"PostgreSQL backup created successfully: {backup_file}")
                    return {
                        'file': str(backup_file),
                        'metadata': metadata
                    }
                else:
                    logger.error(f"PostgreSQL backup failed: {result.stderr}")
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
            
            # Check if this is a SQLite or PostgreSQL backup
            database_type = backup['metadata'].get('database', '')
            
            if database_type == 'sqlite':
                # Handle SQLite restoration
                try:
                    # Determine destination path - use the path in metadata or fallback to default
                    dest_path = backup['metadata'].get('path')
                    if not dest_path:
                        dest_path = os.path.join(os.getcwd(), 'instance', 'dev.db')
                    
                    # Make sure the directory exists
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    
                    # Connect to backup
                    backup_conn = sqlite3.connect(str(backup_file))
                    # Connect to destination (may or may not exist yet)
                    dest_conn = sqlite3.connect(dest_path)
                    
                    # Backup from source to destination (reverse of create_backup)
                    backup_conn.backup(dest_conn)
                    
                    # Close connections
                    backup_conn.close()
                    dest_conn.close()
                    
                    logger.info(f"Successfully restored SQLite DB from backup: {backup['metadata']['timestamp']}")
                    return True
                except Exception as e:
                    logger.error(f"SQLite restoration failed: {str(e)}")
                    return False
            else:
                # Handle PostgreSQL restoration
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
                    logger.info(f"Successfully restored PostgreSQL DB from backup: {backup['metadata']['timestamp']}")
                    return True
                else:
                    logger.error(f"PostgreSQL restore failed: {result.stderr}")
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
                
                # Check if this is SQLite or PostgreSQL backup
                database_type = metadata.get('database', '')
                
                if database_type == 'sqlite':
                    # For SQLite backups, check .db extension
                    backup_file = self.backup_dir / f"backup_{metadata['timestamp']}.db"
                else:
                    # For PostgreSQL backups, check .sql extension
                    backup_file = self.backup_dir / f"backup_{metadata['timestamp']}.sql"
                
                # Also check for alternative naming - for backward compatibility
                if not backup_file.exists():
                    # Try sqlite_backup_ prefix for SQLite backups
                    alt_backup_file = self.backup_dir / f"sqlite_backup_{metadata['timestamp']}.db"
                    if alt_backup_file.exists():
                        backup_file = alt_backup_file
                
                # Only add if the backup file actually exists
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
