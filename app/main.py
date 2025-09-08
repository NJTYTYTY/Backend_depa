"""
Main FastAPI application for Backend_PWA
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import logging
import asyncio
from datetime import datetime
import json

# Use relative imports for Railway deployment
from .core.config import settings
from .storage import initialize_storage
from .api.endpoints import auth, ponds, sensors, media, testing
from .core.websocket import manager, WebSocketMessage, MessageType

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Create FastAPI app
app = FastAPI(
    title="Backend_PWA",
    description="Backend PWA for Shrimp Farm Management System",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add trusted host middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Configure based on your deployment
)

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Backend_PWA",
        "version": "3.0.0"
    }

# Storage info endpoint
@app.get("/storage-info")
async def storage_info():
    """Storage information endpoint"""
    from .storage import UserStorage, PondStorage
    return {
        "storage_type": "JSON",
        "users_count": UserStorage.count(),
        "ponds_count": PondStorage.count(),
        "status": "healthy"
    }

# WebSocket connection statistics endpoint
@app.get("/ws/stats")
async def websocket_stats():
    """Get WebSocket connection statistics"""
    return manager.get_connection_stats()

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to Backend_PWA",
        "version": "3.0.0",
        "docs": "/docs",
        "health": "/health",
        "db_info": "/db-info",
        "ws_stats": "/ws/stats"
    }

# WebSocket endpoint for real-time data synchronization
@app.websocket("/ws/{pond_id}")
async def websocket_endpoint(
    websocket: WebSocket, 
    pond_id: int, 
    token: str = Query(..., description="JWT token for authentication")
):
    """
    WebSocket endpoint for real-time pond monitoring
    
    Args:
        websocket: WebSocket instance
        pond_id: ID of the pond to monitor
        token: JWT token for authentication
    """
    try:
        # Validate token and get user information
        from .core.security import verify_token
        from .storage import UserStorage, PondStorage
        
        # Verify JWT token
        try:
            token_data = verify_token(token, "access")
            user_id = int(token_data.get("user_id"))
        except Exception as e:
            logging.error(f"Invalid JWT token: {e}")
            await websocket.close(code=4003, reason="Invalid authentication token")
            return
        
        # Verify pond access
        from .storage import UserStorage, PondStorage
        
        # Check if pond exists and user has access
        pond = PondStorage.get_by_id(pond_id)
        if not pond:
            await websocket.close(code=4004, reason="Pond not found")
            return
        
        # Check user access (admin can access all ponds, users can only access their own)
        user = UserStorage.get_by_id(user_id)
        if not user:
            await websocket.close(code=4003, reason="User not found")
            return
        
        if not user.get("is_admin", False) and pond.get("owner_id") != user_id:
            await websocket.close(code=4003, reason="Access denied to this pond")
            return
        
        # Accept WebSocket connection
        await manager.connect(websocket, pond_id, user_id)
        
        # Send initial pond data
        initial_message = WebSocketMessage(
            message_type=MessageType.POND_UPDATE,
            data={
                "pond_id": pond_id,
                "pond_name": pond.get("name", "Unknown"),
                "status": "connected",
                "message": f"Connected to {pond.get('name', 'Unknown')} monitoring"
            },
            pond_id=pond_id,
            user_id=user_id
        )
        await websocket.send_text(initial_message.to_json())
        
        # Start heartbeat loop
        heartbeat_task = asyncio.create_task(heartbeat_loop(websocket))
        
        # Main message loop
        try:
            while True:
                # Wait for messages from client
                data = await websocket.receive_text()
                
                # Update message count
                manager.stats["messages_received"] += 1
                
                # Handle client messages (ping, commands, etc.)
                try:
                    message_data = json.loads(data)
                    message_type = message_data.get("type", "unknown")
                    
                    if message_type == "ping":
                        # Respond to ping with pong
                        pong_message = WebSocketMessage(
                            message_type=MessageType.HEARTBEAT,
                            data={"type": "pong", "timestamp": datetime.utcnow().isoformat()},
                            pond_id=pond_id,
                            user_id=user_id
                        )
                        await websocket.send_text(pong_message.to_json())
                    
                    elif message_type == "command":
                        # Handle client commands
                        command = message_data.get("command")
                        if command == "get_pond_status":
                            # Send current pond status
                            status_message = WebSocketMessage(
                                message_type=MessageType.POND_UPDATE,
                                data={"command": "pond_status", "pond_id": pond_id},
                                pond_id=pond_id,
                                user_id=user_id
                            )
                            await websocket.send_text(status_message.to_json())
                    
                except json.JSONDecodeError:
                    # Handle non-JSON messages
                    logging.warning(f"Received non-JSON message: {data}")
                
        except WebSocketDisconnect:
            logging.info(f"WebSocket disconnected: pond_id={pond_id}, user_id={user_id}")
        finally:
            # Cancel heartbeat task
            heartbeat_task.cancel()
            # Clean up connection
            manager.disconnect(websocket)
            
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass

async def heartbeat_loop(websocket: WebSocket):
    """
    Send periodic heartbeat messages to keep WebSocket connection alive
    
    Args:
        websocket: WebSocket instance to send heartbeats to
    """
    try:
        while True:
            await asyncio.sleep(30)  # Send heartbeat every 30 seconds
            await manager.send_heartbeat(websocket)
    except asyncio.CancelledError:
        # Task was cancelled, exit gracefully
        pass
    except Exception as e:
        logging.error(f"Heartbeat error: {e}")

# Include API routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(ponds.router, prefix="/api/v1")
app.include_router(sensors.router, prefix="/api/v1")
app.include_router(media.router, prefix="/api/v1")
app.include_router(testing.router, prefix="/api/v1")

# Initialize JSON storage on startup
@app.on_event("startup")
async def startup_event():
    """Initialize JSON storage on startup"""
    try:
        initialize_storage()
        logging.info("JSON storage initialized successfully")
    except Exception as e:
        logging.error(f"Failed to initialize JSON storage: {e}")

# Periodic cleanup of inactive WebSocket connections
@app.on_event("startup")
async def start_websocket_cleanup():
    """Start periodic WebSocket connection cleanup"""
    async def cleanup_loop():
        while True:
            try:
                await asyncio.sleep(60)  # Run cleanup every minute
                manager.cleanup_inactive_connections(max_idle_time=300)  # 5 minutes
            except Exception as e:
                logging.error(f"WebSocket cleanup error: {e}")
    
    asyncio.create_task(cleanup_loop())

if __name__ == "__main__":
    import uvicorn
    import os
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        reload=False
    )
