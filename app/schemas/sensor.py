"""
Sensor data schemas for Backend_PWA
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Literal
from datetime import datetime

class SensorDataBase(BaseModel):
    """Base sensor data schema"""
    sensor_type: str = Field(..., description="Type of sensor (temperature, oxygen, ph, etc.)")
    value: float = Field(..., description="Sensor reading value")
    status: Literal['green', 'yellow', 'red'] = Field(default='green', description="Status indicator based on thresholds")
    meta_data: Optional[str] = Field(None, description="Additional sensor metadata")

class SensorDataCreate(SensorDataBase):
    """Schema for creating new sensor data"""
    pond_id: int = Field(..., description="ID of the pond this sensor data belongs to")

class SensorDataUpdate(BaseModel):
    """Schema for updating sensor data"""
    value: Optional[float] = Field(None, description="Updated sensor reading value")
    status: Optional[Literal['green', 'yellow', 'red']] = Field(None, description="Updated status indicator")
    meta_data: Optional[str] = Field(None, description="Updated metadata")

class SensorDataResponse(SensorDataBase):
    """Schema for sensor data response"""
    id: int
    pond_id: int
    timestamp: datetime
    created_at: datetime

    class Config:
        from_attributes = True

class SensorDataList(BaseModel):
    """Schema for list of sensor data with pagination"""
    sensor_data: List[SensorDataResponse]
    total: int
    page: int
    size: int
    total_pages: int

class SensorDataFilter(BaseModel):
    """Schema for filtering sensor data"""
    sensor_type: Optional[str] = Field(None, description="Filter by sensor type")
    status: Optional[Literal['green', 'yellow', 'red']] = Field(None, description="Filter by status")
    min_value: Optional[float] = Field(None, description="Minimum sensor value")
    max_value: Optional[float] = Field(None, description="Maximum sensor value")
    start_date: Optional[datetime] = Field(None, description="Start date for time range")
    end_date: Optional[datetime] = Field(None, description="End date for time range")
    pond_id: Optional[int] = Field(None, description="Filter by specific pond")

    @validator('start_date', 'end_date')
    def validate_date_range(cls, v, values):
        if v is not None and 'start_date' in values and 'end_date' in values:
            if values['start_date'] is not None and values['end_date'] is not None:
                if values['start_date'] > values['end_date']:
                    raise ValueError('start_date cannot be after end_date')
        return v

    @validator('min_value', 'max_value')
    def validate_value_range(cls, v, values):
        if v is not None and 'min_value' in values and 'max_value' in values:
            if values['min_value'] is not None and values['max_value'] is not None:
                if values['min_value'] > values['max_value']:
                    raise ValueError('min_value cannot be greater than max_value')
        return v

class SensorDataAggregation(BaseModel):
    """Schema for sensor data aggregation results"""
    sensor_type: str
    pond_id: int
    period: str  # e.g., "1h", "1d", "1w", "1m"
    min_value: float
    max_value: float
    avg_value: float
    count: int
    green_count: int
    yellow_count: int
    red_count: int
    start_time: datetime
    end_time: datetime

class SensorDataLatest(BaseModel):
    """Schema for latest sensor readings"""
    pond_id: int
    sensor_type: str
    latest_reading: SensorDataResponse
    previous_reading: Optional[SensorDataResponse] = None
    trend: Optional[str] = Field(None, description="Trend: increasing, decreasing, stable")

class SensorDataWebhook(BaseModel):
    """Schema for sensor data webhook from external systems"""
    pond_id: int
    sensor_type: str
    value: float
    timestamp: Optional[datetime] = Field(None, description="Timestamp from sensor (defaults to current time)")
    device_id: Optional[str] = Field(None, description="Device identifier")
    battery_level: Optional[float] = Field(None, description="Device battery level")
    signal_strength: Optional[float] = Field(None, description="Signal strength")
    meta_data: Optional[dict] = Field(None, description="Additional device metadata")

class SensorThreshold(BaseModel):
    """Schema for sensor thresholds configuration"""
    sensor_type: str
    yellow_min: float = Field(..., description="Minimum value for yellow status")
    yellow_max: float = Field(..., description="Maximum value for yellow status")
    red_min: float = Field(..., description="Minimum value for red status")
    red_max: float = Field(..., description="Maximum value for red status")
    unit: str = Field(..., description="Unit of measurement")
    description: Optional[str] = Field(None, description="Description of the threshold")

class SensorThresholdResponse(SensorThreshold):
    """Schema for sensor threshold response"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class SensorDataBulk(BaseModel):
    """Schema for bulk sensor data operations"""
    readings: List[SensorDataCreate]
    batch_id: Optional[str] = Field(None, description="Batch identifier for tracking")

class SensorDataBulkResponse(BaseModel):
    """Schema for bulk sensor data operation response"""
    batch_id: str
    total_processed: int
    successful: int
    failed: int
    errors: List[dict] = Field(default_factory=list, description="List of errors for failed readings")
