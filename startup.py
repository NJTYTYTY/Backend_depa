#!/usr/bin/env python3
"""
Startup script for Railway deployment
"""
import os
import sys
import uvicorn
import logging

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def ensure_vapid_keys():
    """Ensure VAPID keys exist before starting the server"""
    try:
        vapid_keys_file = os.path.join(os.path.dirname(__file__), "vapid_keys.json")
        if not os.path.exists(vapid_keys_file):
            logger.info("VAPID keys not found, generating new ones...")
            from generate_vapid_keys import generate_vapid_keys
            generate_vapid_keys()
            logger.info("VAPID keys generated successfully")
        else:
            logger.info("VAPID keys found, using existing keys")
    except Exception as e:
        logger.error(f"Failed to ensure VAPID keys: {e}")
        # Continue anyway, the app will generate keys at runtime

if __name__ == "__main__":
    logger.info(f"Current directory: {os.getcwd()}")
    logger.info(f"Python path: {sys.path}")
    
    # Ensure VAPID keys exist
    ensure_vapid_keys()
    
    # Get port from environment variable
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting server on port {port}")
    
    # Run the application with absolute import
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )
