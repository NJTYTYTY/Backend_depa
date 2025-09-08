"""
AI insight schemas for Backend_PWA
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class InsightBase(BaseModel):
    """Base insight schema"""
    insight_type: str
    severity: Optional[str] = None  # low, medium, high, critical
    message: str
    confidence: Optional[float] = None
    external_id: Optional[str] = None
    timestamp: datetime

class InsightCreate(InsightBase):
    """Schema for creating a new insight"""
    pond_id: int

class InsightResponse(InsightBase):
    """Schema for insight response"""
    id: int
    pond_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class InsightList(BaseModel):
    """Schema for list of insights"""
    insights: List[InsightResponse]
    total: int
    page: int
    size: int
