#!/usr/bin/env python3
"""
Main entry point for Railway deployment
"""
import os
import sys
import uvicorn
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Also add the app directory to the path
app_dir = os.path.join(current_dir, "app")
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

logger.info(f"Current directory: {current_dir}")
logger.info(f"Python path: {sys.path}")

if __name__ == "__main__":
    try:
        # Get port from environment variable
        port = int(os.environ.get("PORT", 8000))
        logger.info(f"Starting server on port {port}")
        
        # Test import before running
        try:
            from app.main import app
            logger.info("Successfully imported app module")
        except ImportError as e:
            logger.error(f"Failed to import app module: {e}")
            sys.exit(1)
        
        # Run the application with proper module path
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=port,
            reload=False,
            log_level="info"
        )
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)
