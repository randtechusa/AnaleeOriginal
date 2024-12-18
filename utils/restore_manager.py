import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from .backup_manager import DatabaseBackupManager
from tests.rollback_verification import RollbackVerificationTest

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def execute_verified_restore(app, days: int = 6, target_minute: int = 59, target_hour: int = 23) -> Dict[str, Any]:
    """
    Execute a verified restoration to N days ago with comprehensive testing
    
    Returns:
        Dictionary containing restoration results and verification status
    """
    try:
        # Check environment to protect production
        if app.config.get('ENV') == 'production' and app.config.get('PROTECT_PRODUCTION', True):
            logger.error("Cannot perform restoration in production environment when protection is enabled")
            return {
                'status': 'error',
                'message': 'Restoration blocked in protected production environment',
                'timestamp': datetime.now()
            }
            
        # Initialize backup manager with development database if available
        database_url = app.config.get('DEV_DATABASE_URL') or app.config['SQLALCHEMY_DATABASE_URI']
        backup_manager = DatabaseBackupManager(database_url)
        
        # Ensure Chart of Accounts is preserved during restoration
        logger.info("Preserving Chart of Accounts during restoration...")
        try:
            with backup_manager.get_connection() as conn:
                # Create backup of Chart of Accounts if not exists
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS chart_of_accounts_backup AS
                    SELECT *, current_timestamp as backup_timestamp
                    FROM account
                    WHERE category IN (
                        'Assets', 'Liabilities', 'Equity', 'Income', 'Expenses'
                    );
                """)
                
                # Verify Chart of Accounts exists in backup
                account_count = conn.execute("""
                    SELECT COUNT(*) FROM chart_of_accounts_backup
                """).scalar()
                
                if account_count == 0:
                    logger.warning("No Chart of Accounts found in backup, copying from production...")
                    conn.execute("""
                        INSERT INTO chart_of_accounts_backup
                        SELECT *, current_timestamp as backup_timestamp
                        FROM account
                        WHERE category IN (
                            'Assets', 'Liabilities', 'Equity', 'Income', 'Expenses'
                        );
                    """)
        except Exception as e:
            logger.error(f"Error preserving Chart of Accounts: {str(e)}")
            raise
        
        # Calculate target timestamp
        target_date = datetime.now() - timedelta(days=days)
        target_timestamp = target_date.replace(
            hour=target_hour,
            minute=target_minute,
            second=59,
            microsecond=999999
        )
        
        logger.info(f"Starting verified restoration to {target_timestamp}")
        
        # Initialize verification suite
        verification = RollbackVerificationTest(app)
        
        # Execute restoration
        restore_success = backup_manager.restore_to_days_ago(days, target_minute, target_hour)
        if not restore_success:
            return {
                'status': 'error',
                'message': 'Restoration failed',
                'timestamp': datetime.now()
            }
            
        # Run verification suite
        verification_results = verification.run_all_verifications(target_timestamp)
        
        # Aggregate results
        success = all(result['success'] for result in verification_results.values())
        
        return {
            'status': 'success' if success else 'warning',
            'message': 'Restoration completed successfully' if success else 'Restoration completed with warnings',
            'timestamp': datetime.now(),
            'target_timestamp': target_timestamp,
            'verification_results': verification_results
        }
        
    except Exception as e:
        logger.error(f"Error during verified restoration: {str(e)}")
        return {
            'status': 'error',
            'message': f"Error during restoration: {str(e)}",
            'timestamp': datetime.now()
        }
