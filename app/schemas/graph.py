"""
Graph data schemas for sensor visualization
"""

from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class GraphDataPoint(BaseModel):
    """Single data point for graph visualization"""
    timestamp: datetime
    value: float
    status: Optional[str] = None

class GraphDataResponse(BaseModel):
    """Response containing graph data for a specific sensor type"""
    sensor_type: str
    data_points: List[GraphDataPoint]
    unit: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    average_value: Optional[float] = None
    trend: Optional[str] = None  # 'increasing', 'decreasing', 'stable'

class MultiSensorGraphResponse(BaseModel):
    """Response containing graph data for multiple sensor types"""
    pond_id: int
    sensors: Dict[str, GraphDataResponse]
    time_range: Dict[str, datetime]  # start_time, end_time
    total_points: int
