"""Application entry point"""
from app import create_app
import logging
import os
import sys
import signal

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    logger.info("Shutdown signal received")
    sys.exit(0)

def main():
    """Application startup"""
    try:
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        logger.info("Starting application initialization")
        app = create_app()

        if not app:
            logger.error("Application creation failed - app is None")
            raise ValueError("Application creation failed")

        # Use different port to avoid conflicts
        port = int(os.environ.get('PORT', 3000))
        logger.info(f"Starting Flask server on port {port}")

        app.run(
            host='0.0.0.0',
            port=port,
            debug=False  # Disable debug mode for stability
        )

    except Exception as e:
        logger.error(f"Startup failed: {str(e)}")
        logger.exception("Full startup error traceback:")
        sys.exit(1)

if __name__ == "__main__":
    main()