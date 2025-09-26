"""
Alert schemas for the Shrimp Farm Alert System
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class AlertType(str, Enum):
    """Alert types supported by the system"""
    ITEM_RUNOUT = "Item-runout"
    SHRIMP_ON_WATER = "ShrimpOnWater"

class AlertStatus(str, Enum):
    """Alert status states"""
    UNREAD = "unread"
    READ = "read"
    DISMISSED = "dismissed"

class AlertSeverity(str, Enum):
    """Alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AlertData(BaseModel):
    """Base alert data structure"""
    id: str = Field(..., description="Unique alert ID")
    alert_type: str = Field(..., description="Type of alert (Item-runout-[id] or ShrimpOnWater-[id])")
    pond_id: int = Field(..., description="Pond ID this alert is for")
    user_id: int = Field(..., description="User ID who should receive this alert")
    title: str = Field(..., description="Alert title")
    body: str = Field(..., description="Alert message body")
    status: AlertStatus = Field(default=AlertStatus.UNREAD, description="Alert status")
    severity: AlertSeverity = Field(default=AlertSeverity.MEDIUM, description="Alert severity")
    image_url: Optional[str] = Field(None, description="Image URL for the alert")
    target_url: Optional[str] = Field(None, description="URL to open when alert is clicked")
    data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional alert data")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Alert creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Alert last update timestamp")
    read_at: Optional[datetime] = Field(None, description="When alert was marked as read")

class AlertCreateRequest(BaseModel):
    """Request to create a new alert"""
    alert_type: str = Field(..., description="Alert type pattern (e.g., Item-runout-[1])")
    pond_id: int = Field(..., description="Pond ID")
    user_id: int = Field(..., description="User ID")
    title: str = Field(..., description="Alert title")
    body: str = Field(..., description="Alert message")
    severity: AlertSeverity = Field(default=AlertSeverity.MEDIUM, description="Alert severity")
    image_url: Optional[str] = Field(None, description="Image URL")
    target_url: Optional[str] = Field(None, description="Target URL")
    data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional data")

class AlertUpdateRequest(BaseModel):
    """Request to update an alert"""
    status: Optional[AlertStatus] = Field(None, description="New alert status")
    read_at: Optional[datetime] = Field(None, description="Read timestamp")

class AlertResponse(BaseModel):
    """Alert response structure"""
    success: bool = Field(..., description="Request success status")
    message: str = Field(..., description="Response message")
    data: Optional[AlertData] = Field(None, description="Alert data")
    alerts: Optional[List[AlertData]] = Field(None, description="List of alerts")

class AlertListResponse(BaseModel):
    """Alert list response structure"""
    success: bool = Field(..., description="Request success status")
    message: str = Field(..., description="Response message")
    alerts: List[AlertData] = Field(..., description="List of alerts")
    total_count: int = Field(..., description="Total number of alerts")
    unread_count: int = Field(..., description="Number of unread alerts")

class AlertStatsResponse(BaseModel):
    """Alert statistics response"""
    success: bool = Field(..., description="Request success status")
    total_alerts: int = Field(..., description="Total alerts count")
    unread_alerts: int = Field(..., description="Unread alerts count")
    alerts_by_type: Dict[str, int] = Field(..., description="Alerts count by type")
    alerts_by_pond: Dict[int, int] = Field(..., description="Alerts count by pond")
    alerts_by_severity: Dict[str, int] = Field(..., description="Alerts count by severity")

def parse_alert_type(alert_type: str) -> tuple[str, Optional[str]]:
    """
    Parse alert type string to extract base type and ID
    
    Args:
        alert_type: Alert type string (e.g., "Item-runout-[1]", "ShrimpOnWater-[2]")
    
    Returns:
        tuple: (base_type, id) or (base_type, None) if no ID found
    """
    if "-[" in alert_type and "]" in alert_type:
        # Extract ID from pattern like "Item-runout-[1]"
        start = alert_type.find("-[") + 2
        end = alert_type.find("]", start)
        if start > 1 and end > start:
            base_type = alert_type[:start-2]
            alert_id = alert_type[start:end]
            return base_type, alert_id
    
    # No ID found, return as is
    return alert_type, None

def create_alert_id(alert_type: str, pond_id: int, user_id: int) -> str:
    """
    Create unique alert ID
    
    Args:
        alert_type: Alert type string
        pond_id: Pond ID
        user_id: User ID
    
    Returns:
        str: Unique alert ID
    """
    import time
    timestamp = int(time.time() * 1000)
    return f"alert_{alert_type}_{pond_id}_{user_id}_{timestamp}"
