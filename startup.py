#!/usr/bin/env python3
"""
Startup script for Railway deployment
"""
import os
import sys
import uvicorn

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    # Get port from environment variable
    port = int(os.environ.get("PORT", 8000))
    
    # Run the application with absolute import
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )
