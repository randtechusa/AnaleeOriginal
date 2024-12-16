from datetime import datetime
from flask import current_app
from utils.restore_manager import execute_verified_restore
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Execute restoration to last minute of six days ago"""
    try:
        logger.info("Starting restoration process...")
        
        # Execute restoration with verification
        result = execute_verified_restore(
            current_app,
            days=6,
            target_minute=59,  # Last minute
            target_hour=23     # Last hour
        )
        
        # Log results
        if result['status'] == 'success':
            logger.info(f"Restoration successful to {result['target_timestamp']}")
            for check, details in result['verification_results'].items():
                status = 'Passed' if details['success'] else 'Failed'
                logger.info(f"{check}: {status}")
                if not details['success']:
                    logger.error(f"Error in {check}: {details['error']}")
        else:
            logger.error(f"Restoration failed: {result['message']}")
            
        return result
        
    except Exception as e:
        logger.error(f"Critical error during restoration: {str(e)}")
        return {
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now()
        }

if __name__ == "__main__":
    main()
