"""
Pond schemas for Backend_PWA
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime

class PondBase(BaseModel):
    """Base pond schema"""
    name: str = Field(..., min_length=1, max_length=255, description="Pond name")
    size: Optional[float] = Field(None, gt=0, description="Pond size in square meters")
    location: Optional[str] = Field(None, max_length=500, description="Pond location")
    notes: Optional[str] = Field(None, description="Additional notes about the pond")
    date: Optional[str] = Field(None, description="Date when pond was created")
    dimensions: Optional[str] = Field(None, description="Pond dimensions")
    depth: Optional[float] = Field(None, gt=0, description="Pond depth in meters")
    shrimp_count: Optional[int] = Field(0, ge=0, description="Number of shrimp released in the pond")

class PondCreate(PondBase):
    """Schema for creating a new pond"""
    pass

class PondUpdate(BaseModel):
    """Schema for updating a pond"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    size: Optional[float] = Field(None, gt=0)
    location: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None
    date: Optional[str] = None
    dimensions: Optional[str] = None
    depth: Optional[float] = Field(None, gt=0)
    shrimp_count: Optional[int] = Field(None, ge=0)

class PondResponse(PondBase):
    """Schema for pond response"""
    id: int
    owner_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    shrimp_count: Optional[int] = Field(0, ge=0, description="Number of shrimp released in the pond")

    class Config:
        from_attributes = True

class PondList(BaseModel):
    """Schema for list of ponds with pagination"""
    ponds: List[PondResponse]
    total: int
    skip: int
    limit: int

class PondFilter(BaseModel):
    """Schema for filtering ponds"""
    name: Optional[str] = Field(None, description="Filter by pond name (partial match)")
    min_size: Optional[float] = Field(None, ge=0, description="Minimum pond size")
    max_size: Optional[float] = Field(None, ge=0, description="Maximum pond size")
    location: Optional[str] = Field(None, description="Filter by location (partial match)")
    owner_id: Optional[int] = Field(None, description="Filter by owner ID")

    @validator('min_size', 'max_size')
    def validate_size_range(cls, v, values):
        if v is not None and 'min_size' in values and 'max_size' in values:
            if values['min_size'] is not None and values['max_size'] is not None:
                if values['min_size'] > values['max_size']:
                    raise ValueError('min_size cannot be greater than max_size')
        return v

class PondStats(BaseModel):
    """Schema for pond statistics"""
    pond_id: int
    total_sensor_readings: int
    last_sensor_reading: Optional[datetime]
    media_count: int
    insights_count: int
    control_logs_count: int

class PondDetail(PondResponse):
    """Schema for detailed pond information"""
    owner: dict = Field(..., description="Owner information")
    sensor_count: int = Field(0, description="Number of sensor readings")
    media_count: int = Field(0, description="Number of media assets")
    insight_count: int = Field(0, description="Number of AI insights")
    last_activity: Optional[datetime] = Field(None, description="Last activity timestamp")
