
"""Application entry point"""
from app import create_app
import logging
import os
import sys

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

def main():
    """Application startup"""
    try:
        logger.info("Starting application")
        app = create_app()
        
        if not app:
            raise ValueError("Application creation failed")
            
        port = int(os.environ.get('PORT', 3000))
        logger.info(f"Starting server on port {port}")
        
        app.run(
            host='0.0.0.0',
            port=port,
            debug=True
        )
        
    except Exception as e:
        logger.error(f"Startup failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
