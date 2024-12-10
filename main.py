from app import app
import logging

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        logger.info("Starting Flask application...")
        app.run(
            host="0.0.0.0",
            port=5000,
            debug=True,
            use_reloader=False  # Disable reloader to avoid duplicate startups
        )
    except Exception as e:
        logger.error(f"Failed to start Flask application: {str(e)}")
        logger.exception("Full stack trace:")
        raise
