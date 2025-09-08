"""
WebSocket connection manager for real-time data synchronization
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List, Optional, Set
import json
import logging
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

class MessageType(Enum):
    """Message types for WebSocket communication"""
    SENSOR_UPDATE = "sensor_update"
    POND_UPDATE = "pond_update"
    SYSTEM_ALERT = "system_alert"
    HEARTBEAT = "heartbeat"
    AUTHENTICATION = "authentication"
    ERROR = "error"

class ConnectionStatus(Enum):
    """Connection status enumeration"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    AUTHENTICATED = "authenticated"
    UNAUTHORIZED = "unauthorized"

class WebSocketMessage:
    """WebSocket message structure"""
    def __init__(
        self,
        message_type: MessageType,
        data: dict,
        timestamp: Optional[datetime] = None,
        pond_id: Optional[int] = None,
        user_id: Optional[int] = None
    ):
        self.message_type = message_type
        self.data = data
        self.timestamp = timestamp or datetime.utcnow()
        self.pond_id = pond_id
        self.user_id = user_id
    
    def to_dict(self) -> dict:
        """Convert message to dictionary"""
        return {
            "type": self.message_type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "pond_id": self.pond_id,
            "user_id": self.user_id
        }
    
    def to_json(self) -> str:
        """Convert message to JSON string"""
        return json.dumps(self.to_dict())

class ConnectionManager:
    """
    Manages WebSocket connections for real-time data synchronization
    """
    
    def __init__(self):
        # Active connections organized by pond_id
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # User connection mapping for authentication
        self.user_connections: Dict[int, Set[WebSocket]] = {}
        # Connection metadata
        self.connection_metadata: Dict[WebSocket, dict] = {}
        # Connection statistics
        self.stats = {
            "total_connections": 0,
            "active_connections": 0,
            "ponds_with_connections": 0,
            "messages_sent": 0,
            "messages_received": 0
        }
    
    async def connect(self, websocket: WebSocket, pond_id: int, user_id: Optional[int] = None):
        """
        Accept a new WebSocket connection
        
        Args:
            websocket: WebSocket instance
            pond_id: ID of the pond to monitor
            user_id: ID of the authenticated user
        """
        try:
            await websocket.accept()
            
            # Initialize pond connections if not exists
            if pond_id not in self.active_connections:
                self.active_connections[pond_id] = set()
                self.stats["ponds_with_connections"] = len(self.active_connections)
            
            # Add connection to pond
            self.active_connections[pond_id].add(websocket)
            
            # Track user connection if authenticated
            if user_id:
                if user_id not in self.user_connections:
                    self.user_connections[user_id] = set()
                self.user_connections[user_id].add(websocket)
            
            # Store connection metadata
            self.connection_metadata[websocket] = {
                "pond_id": pond_id,
                "user_id": user_id,
                "connected_at": datetime.utcnow(),
                "status": ConnectionStatus.CONNECTED,
                "last_heartbeat": datetime.utcnow(),
                "message_count": 0
            }
            
            # Update statistics
            self.stats["total_connections"] += 1
            self.stats["active_connections"] += 1
            
            logger.info(f"WebSocket connected: pond_id={pond_id}, user_id={user_id}, total_connections={self.stats['active_connections']}")
            
            # Send welcome message
            welcome_message = WebSocketMessage(
                message_type=MessageType.AUTHENTICATION,
                data={"status": "connected", "pond_id": pond_id},
                pond_id=pond_id,
                user_id=user_id
            )
            await websocket.send_text(welcome_message.to_json())
            
        except Exception as e:
            logger.error(f"Failed to accept WebSocket connection: {e}")
            raise
    
    def disconnect(self, websocket: WebSocket):
        """
        Remove a WebSocket connection
        
        Args:
            websocket: WebSocket instance to disconnect
        """
        try:
            # Get connection metadata
            metadata = self.connection_metadata.get(websocket, {})
            pond_id = metadata.get("pond_id")
            user_id = metadata.get("user_id")
            
            # Remove from pond connections
            if pond_id and pond_id in self.active_connections:
                self.active_connections[pond_id].discard(websocket)
                
                # Remove empty pond entry
                if not self.active_connections[pond_id]:
                    del self.active_connections[pond_id]
                    self.stats["ponds_with_connections"] = len(self.active_connections)
            
            # Remove from user connections
            if user_id and user_id in self.user_connections:
                self.user_connections[user_id].discard(websocket)
                
                # Remove empty user entry
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
            
            # Remove metadata
            if websocket in self.connection_metadata:
                del self.connection_metadata[websocket]
            
            # Update statistics
            self.stats["active_connections"] = max(0, self.stats["active_connections"] - 1)
            
            logger.info(f"WebSocket disconnected: pond_id={pond_id}, user_id={user_id}, active_connections={self.stats['active_connections']}")
            
        except Exception as e:
            logger.error(f"Error during WebSocket disconnect: {e}")
    
    async def broadcast_to_pond(self, pond_id: int, message: WebSocketMessage):
        """
        Broadcast a message to all connections monitoring a specific pond
        
        Args:
            pond_id: ID of the pond to broadcast to
            message: WebSocketMessage to broadcast
        """
        if pond_id not in self.active_connections:
            return
        
        disconnected_websockets = set()
        message_json = message.to_json()
        
        for websocket in self.active_connections[pond_id]:
            try:
                await websocket.send_text(message_json)
                
                # Update connection metadata
                if websocket in self.connection_metadata:
                    self.connection_metadata[websocket]["message_count"] += 1
                
                self.stats["messages_sent"] += 1
                
            except WebSocketDisconnect:
                disconnected_websockets.add(websocket)
            except Exception as e:
                logger.error(f"Failed to send message to WebSocket: {e}")
                disconnected_websockets.add(websocket)
        
        # Clean up disconnected websockets
        for websocket in disconnected_websockets:
            self.disconnect(websocket)
    
    async def broadcast_to_user(self, user_id: int, message: WebSocketMessage):
        """
        Broadcast a message to all connections of a specific user
        
        Args:
            user_id: ID of the user to broadcast to
            message: WebSocketMessage to broadcast
        """
        if user_id not in self.user_connections:
            return
        
        disconnected_websockets = set()
        message_json = message.to_json()
        
        for websocket in self.user_connections[user_id]:
            try:
                await websocket.send_text(message_json)
                
                # Update connection metadata
                if websocket in self.connection_metadata:
                    self.connection_metadata[websocket]["message_count"] += 1
                
                self.stats["messages_sent"] += 1
                
            except WebSocketDisconnect:
                disconnected_websockets.add(websocket)
            except Exception as e:
                logger.error(f"Failed to send message to WebSocket: {e}")
                disconnected_websockets.add(websocket)
        
        # Clean up disconnected websockets
        for websocket in disconnected_websockets:
            self.disconnect(websocket)
    
    async def broadcast_system_alert(self, message: str, alert_level: str = "info"):
        """
        Broadcast a system alert to all connected clients
        
        Args:
            message: Alert message
            alert_level: Alert level (info, warning, error, critical)
        """
        alert_message = WebSocketMessage(
            message_type=MessageType.SYSTEM_ALERT,
            data={"message": message, "level": alert_level}
        )
        
        # Broadcast to all ponds
        for pond_id in list(self.active_connections.keys()):
            await self.broadcast_to_pond(pond_id, alert_message)
    
    async def send_heartbeat(self, websocket: WebSocket):
        """
        Send heartbeat message to keep connection alive
        
        Args:
            websocket: WebSocket instance to send heartbeat to
        """
        try:
            heartbeat_message = WebSocketMessage(
                message_type=MessageType.HEARTBEAT,
                data={"timestamp": datetime.utcnow().isoformat()}
            )
            await websocket.send_text(heartbeat_message.to_json())
            
            # Update last heartbeat
            if websocket in self.connection_metadata:
                self.connection_metadata[websocket]["last_heartbeat"] = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Failed to send heartbeat: {e}")
    
    def get_connection_info(self, websocket: WebSocket) -> Optional[dict]:
        """
        Get information about a specific connection
        
        Args:
            websocket: WebSocket instance
            
        Returns:
            Connection metadata or None if not found
        """
        return self.connection_metadata.get(websocket)
    
    def get_pond_connections_count(self, pond_id: int) -> int:
        """
        Get the number of active connections for a specific pond
        
        Args:
            pond_id: ID of the pond
            
        Returns:
            Number of active connections
        """
        return len(self.active_connections.get(pond_id, set()))
    
    def get_user_connections_count(self, user_id: int) -> int:
        """
        Get the number of active connections for a specific user
        
        Args:
            user_id: ID of the user
            
        Returns:
            Number of active connections
        """
        return len(self.user_connections.get(user_id, set()))
    
    def get_connection_stats(self) -> dict:
        """
        Get connection statistics
        
        Returns:
            Dictionary with connection statistics
        """
        return {
            **self.stats,
            "ponds_with_connections": len(self.active_connections),
            "users_with_connections": len(self.user_connections),
            "total_metadata_entries": len(self.connection_metadata)
        }
    
    def cleanup_inactive_connections(self, max_idle_time: int = 300):
        """
        Clean up inactive connections (for periodic maintenance)
        
        Args:
            max_idle_time: Maximum idle time in seconds before cleanup
        """
        current_time = datetime.utcnow()
        websockets_to_remove = set()
        
        for websocket, metadata in self.connection_metadata.items():
            last_heartbeat = metadata.get("last_heartbeat")
            if last_heartbeat:
                idle_time = (current_time - last_heartbeat).total_seconds()
                if idle_time > max_idle_time:
                    websockets_to_remove.add(websocket)
        
        for websocket in websockets_to_remove:
            logger.info(f"Cleaning up inactive connection: {websocket}")
            self.disconnect(websocket)

# Global connection manager instance
manager = ConnectionManager()
