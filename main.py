from app import create_app
import logging
import os

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        # Configure more detailed logging
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        logger.info("Creating Flask application...")
        app = create_app()
        
        # Get port from environment or default to 5000
        port = int(os.environ.get('PORT', 5000))
        logger.info(f"Using port: {port}")
        
        logger.info("Starting Flask application...")
        app.run(
            host='0.0.0.0',  # Required for Replit
            port=port,
            debug=True,      # Enable debug mode
            use_reloader=False  # Disable reloader to avoid duplicate startups
        )
    except Exception as e:
        logger.error(f"Failed to start Flask application: {str(e)}")
        logger.exception("Full stack trace:")
        raise
