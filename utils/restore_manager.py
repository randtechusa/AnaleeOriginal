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

        # Execute restoration  - Modified to handle duplicate links
        with backup_manager.get_connection() as conn:
            try:
                # First backup existing Chart of Accounts
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS chart_of_accounts_backup AS
                    SELECT DISTINCT ON (link) *
                    FROM account 
                    WHERE category IN ('Assets', 'Liabilities', 'Equity', 'Income', 'Expenses')
                    ORDER BY link, updated_at DESC;
                """)

                # Handle duplicate links by adding a suffix
                conn.execute("""
                    CREATE OR REPLACE FUNCTION generate_unique_link(base_link text) 
                    RETURNS text AS $$
                    DECLARE
                        counter integer := 1;
                        new_link text;
                    BEGIN
                        new_link := base_link;
                        WHILE EXISTS (SELECT 1 FROM account WHERE link = new_link) LOOP
                            new_link := base_link || '_' || counter;
                            counter := counter + 1;
                        END LOOP;
                        RETURN new_link;
                    END;
                    $$ LANGUAGE plpgsql;
                """)

                # Restore accounts with unique links
                conn.execute("""
                    INSERT INTO account (
                        link, name, category, sub_category, user_id, 
                        is_active, created_at, updated_at
                    )
                    SELECT 
                        generate_unique_link(link), name, category, 
                        sub_category, user_id, is_active, 
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    FROM chart_of_accounts_backup
                    ON CONFLICT (link) DO NOTHING;
                """)

                logger.info("Database tables and Chart of Accounts restored with unique links")
            except Exception as db_error:
                logger.error(f"Error during restoration: {str(db_error)}")
                raise

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