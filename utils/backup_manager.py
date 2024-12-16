import os
import logging
import json
from datetime import datetime
from pathlib import Path
import subprocess
from flask_apscheduler import APScheduler
from sqlalchemy import create_engine, text

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseBackupManager:
    def __init__(self, db_url, backup_dir="backups"):
        self.db_url = db_url
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        self.engine = create_engine(db_url)
        
    def create_backup(self):
        """Create a backup of the current database state"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = self.backup_dir / f"backup_{timestamp}.sql"
            
            # Get database connection details from URL
            db_info = {
                'host': os.environ.get('PGHOST'),
                'port': os.environ.get('PGPORT'),
                'user': os.environ.get('PGUSER'),
                'password': os.environ.get('PGPASSWORD'),
                'database': os.environ.get('PGDATABASE')
            }
            
            # Create backup using pg_dump
            cmd = [
                'pg_dump',
                f"--host={db_info['host']}",
                f"--port={db_info['port']}",
                f"--username={db_info['user']}",
                f"--dbname={db_info['database']}",
                '--format=c',
                f"--file={backup_file}"
            ]
            
            env = os.environ.copy()
            env['PGPASSWORD'] = db_info['password']
            
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"Successfully created backup: {backup_file}")
                # Create metadata file
                metadata = {
                    'timestamp': timestamp,
                    'database': db_info['database'],
                    'size': os.path.getsize(backup_file),
                    'type': 'automated'
                }
                metadata_file = self.backup_dir / f"backup_{timestamp}_metadata.json"
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f, indent=2)
                return str(backup_file)
            else:
                logger.error(f"Backup failed: {result.stderr}")
                raise Exception(f"Backup failed: {result.stderr}")
                
        except Exception as e:
            logger.error(f"Error creating backup: {str(e)}")
            raise
            
    def list_backups(self):
        """List all available backups with their metadata"""
        backups = []
        for metadata_file in self.backup_dir.glob('*_metadata.json'):
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                backup_file = self.backup_dir / f"backup_{metadata['timestamp']}.sql"
                if backup_file.exists():
                    backups.append({
                        'file': str(backup_file),
                        'metadata': metadata
                    })
            except Exception as e:
                logger.error(f"Error reading backup metadata {metadata_file}: {str(e)}")
                
        return sorted(backups, key=lambda x: x['metadata']['timestamp'], reverse=True)
        
    def verify_backup(self, backup_file):
        """Verify the integrity of a backup file"""
        try:
            cmd = [
                'pg_restore',
                '--list',
                str(backup_file)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Error verifying backup {backup_file}: {str(e)}")
            return False
            
    def find_closest_backup(self, target_timestamp: datetime) -> Optional[dict]:
        """Find the backup closest to the target timestamp"""
        try:
            backups = self.list_backups()
            if not backups:
                logger.error("No backups available")
                return None
                
            closest_backup = min(
                backups,
                key=lambda x: abs(
                    datetime.strptime(x['metadata']['timestamp'], '%Y%m%d_%H%M%S') - target_timestamp
                )
            )
            
            backup_time = datetime.strptime(closest_backup['metadata']['timestamp'], '%Y%m%d_%H%M%S')
            logger.info(f"Found closest backup from {backup_time}")
            return closest_backup
            
        except Exception as e:
            logger.error(f"Error finding closest backup: {str(e)}")
            return None
            
    def restore_to_timestamp(self, target_timestamp: datetime) -> bool:
        """Restore database to the state closest to the target timestamp"""
        try:
            backup = self.find_closest_backup(target_timestamp)
            if not backup:
                logger.error("No suitable backup found for restoration")
                return False
                
            backup_file = Path(backup['file'])
            if not backup_file.exists():
                logger.error(f"Backup file {backup_file} not found")
                return False
                
            # Get database connection details
            db_info = {
                'host': os.environ.get('PGHOST'),
                'port': os.environ.get('PGPORT'),
                'user': os.environ.get('PGUSER'),
                'password': os.environ.get('PGPASSWORD'),
                'database': os.environ.get('PGDATABASE')
            }
            
            # Drop existing connections
            with self.engine.connect() as conn:
                conn.execute(text(
                    """
                    SELECT pg_terminate_backend(pid) 
                    FROM pg_stat_activity 
                    WHERE datname = :database 
                    AND pid <> pg_backend_pid()
                    """
                ), {'database': db_info['database']})
                
            # Restore using pg_restore
            cmd = [
                'pg_restore',
                '--clean',

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

                '--if-exists',
                f"--host={db_info['host']}",
                f"--port={db_info['port']}",
                f"--username={db_info['user']}",
                f"--dbname={db_info['database']}",
                str(backup_file)
            ]
            
            env = os.environ.copy()
            env['PGPASSWORD'] = db_info['password']
            
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
