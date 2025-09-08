"""
Control action schemas for Backend_PWA
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ControlActionBase(BaseModel):
    """Base control action schema"""
    control_type: str  # aerator, light, feeder
    action: str  # on, off, adjust
    value: Optional[float] = None  # For adjustable controls

class ControlActionCreate(ControlActionBase):
    """Schema for creating a new control action"""
    pond_id: int

class ControlLogResponse(ControlActionBase):
    """Schema for control log response"""
    id: int
    pond_id: int
    user_id: int
    status: str  # pending, completed, failed
    external_id: Optional[str] = None
    timestamp: datetime
    created_at: datetime

    class Config:
        from_attributes = True

class ControlLogList(BaseModel):
    """Schema for list of control logs"""
    control_logs: List[ControlLogResponse]
    total: int
    page: int
    size: int
