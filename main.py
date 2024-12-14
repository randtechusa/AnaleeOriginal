from app import create_app
import logging
import os
import sys

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def main():
    try:
        logger.info("Starting application initialization...")
        
        # Initialize the Flask application
        app = create_app()
        if not app:
            raise ValueError("Application creation failed")
        logger.info("Application created successfully")
        
        # Get port from environment or default to 5000
        port = int(os.environ.get('PORT', 5000))
        logger.info(f"Using port: {port}")
        
        # Start the Flask development server
        app.run(
            host='0.0.0.0',
            port=port,
            debug=True,
            use_reloader=False  # Disable reloader to prevent duplicate processes
        )
        
    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}")
        logger.exception("Full stack trace:")
        sys.exit(1)

if __name__ == "__main__":
    main()
