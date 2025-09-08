"""
Sensor data management endpoints for Backend_PWA
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from datetime import datetime, timedelta
import logging

from ...storage import SensorReadingStorage, PondStorage
from ...schemas.sensor import (
    SensorDataCreate, 
    SensorDataUpdate, 
    SensorDataResponse, 
    SensorDataList,
    SensorDataFilter,
    SensorDataAggregation,
    SensorDataLatest,
    SensorDataWebhook,
    SensorThreshold,
    SensorThresholdResponse,
    SensorDataBulk,
    SensorDataBulkResponse
)
from ...api.dependencies import (
    get_current_active_user,
    get_admin_user
)
from ...api.endpoints.ponds import verify_pond_ownership
from ...core.websocket import manager, WebSocketMessage, MessageType

router = APIRouter(prefix="/sensors", tags=["sensors"])

# Configure logging
logger = logging.getLogger(__name__)

def calculate_sensor_status(sensor_type: str, value: float) -> str:
    """
    Calculate sensor status based on thresholds
    Returns: 'green', 'yellow', or 'red'
    """
    # Default thresholds (should be configurable from database)
    thresholds = {
        'temperature': {
            'yellow': [(25, 32)],  # (min, max) for yellow
            'red': [(0, 24), (33, 100)]  # ranges for red
        },
        'oxygen': {
            'yellow': [(3, 5)],
            'red': [(0, 2.9)]
        },
        'ph': {
            'yellow': [(6.5, 7.0), (8.5, 9.0)],
            'red': [(0, 6.4), (9.1, 14)]
        },
        'salinity': {
            'yellow': [(15, 20), (35, 40)],
            'red': [(0, 14.9), (40.1, 50)]
        },
        'turbidity': {
            'yellow': [(10, 20)],
            'red': [(0, 9.9), (20.1, 100)]
        }
    }
    
    if sensor_type in thresholds:
        # Check red status first
        for min_val, max_val in thresholds[sensor_type]['red']:
            if min_val <= value <= max_val:
                return 'red'
        
        # Check yellow status
        for min_val, max_val in thresholds[sensor_type]['yellow']:
            if min_val <= value <= max_val:
                return 'yellow'
    
    return 'green'

def verify_sensor_data_access(
    pond_id: int, 
    current_user: dict, 
) -> dict:
    """
    Verify access to sensor data for a specific pond
    """
    from ...api.dependencies import verify_pond_ownership
    return verify_pond_ownership(pond_id, current_user)

async def broadcast_sensor_update(
    pond_id: int,
    sensor_data: dict,
    status: str,
    user_id: Optional[int] = None
):
    """
    Broadcast sensor update to WebSocket clients monitoring the pond
    
    Args:
        pond_id: ID of the pond
        sensor_data: Sensor data to broadcast
        status: Calculated status (green/yellow/red)
        user_id: ID of the user who submitted the data
    """
    try:
        # Create WebSocket message
        message = WebSocketMessage(
            message_type=MessageType.SENSOR_UPDATE,
            data={
                "sensor_type": sensor_data["sensor_type"],
                "value": sensor_data["value"],
                "status": status,
                "timestamp": datetime.utcnow().isoformat(),
                "meta_data": sensor_data.get("meta_data"),
                "user_id": user_id
            },
            pond_id=pond_id,
            user_id=user_id
        )
        
        # Broadcast to all clients monitoring this pond
        await manager.broadcast_to_pond(pond_id, message)
        
        logger.info(f"Broadcasted sensor update: {sensor_data['sensor_type']}={sensor_data['value']} (status: {status}) to pond {pond_id}")
        
    except Exception as e:
        logger.error(f"Failed to broadcast sensor update: {e}")

@router.post("/data", response_model=SensorDataResponse, status_code=status.HTTP_201_CREATED)
async def create_sensor_data(
    sensor_data: SensorDataCreate,
    current_user: dict = Depends(get_current_active_user),
):
    """
    Create new sensor data reading
    """
    # Verify pond access
    verify_sensor_data_access(sensor_data.pond_id, current_user, db)
    
    # Calculate status based on value
    calculated_status = calculate_sensor_status(sensor_data.sensor_type, sensor_data.value)
    
    # Create sensor reading
    db_sensor_data = SensorReading(
        pond_id=sensor_data.pond_id,
        sensor_type=sensor_data.sensor_type,
        value=sensor_data.value,
        status=calculated_status,
        meta_data=sensor_data.meta_data,
        timestamp=datetime.utcnow()
    )
    
    db.add(db_sensor_data)
    db.commit()
    db.refresh(db_sensor_data)
    
    logger.info(f"Created sensor data: {sensor_data.sensor_type}={sensor_data.value} for pond {sensor_data.pond_id}")
    
    # Broadcast update to WebSocket clients
    await broadcast_sensor_update(
        pond_id=sensor_data.pond_id,
        sensor_data=sensor_data.dict(),
        status=calculated_status,
        user_id=current_user.id
    )
    
    return db_sensor_data

@router.post("/webhook", response_model=SensorDataResponse, status_code=status.HTTP_201_CREATED)
async def receive_sensor_webhook(
    webhook_data: SensorDataWebhook,
    current_user: dict = Depends(get_current_active_user),
):
    """
    Receive sensor data from external systems (webhook)
    """
    # Verify pond access
    verify_sensor_data_access(webhook_data.pond_id, current_user, db)
    
    # Use provided timestamp or current time
    timestamp = webhook_data.timestamp or datetime.utcnow()
    
    # Calculate status based on value
    calculated_status = calculate_sensor_status(webhook_data.sensor_type, webhook_data.value)
    
    # Create sensor reading
    db_sensor_data = SensorReading(
        pond_id=webhook_data.pond_id,
        sensor_type=webhook_data.sensor_type,
        value=webhook_data.value,
        status=calculated_status,
        meta_data=str(webhook_data.meta_data) if webhook_data.meta_data else None,
        timestamp=timestamp
    )
    
    db.add(db_sensor_data)
    db.commit()
    db.refresh(db_sensor_data)
    
    logger.info(f"Received webhook: {webhook_data.sensor_type}={webhook_data.value} for pond {webhook_data.pond_id}")
    
    # Broadcast update to WebSocket clients
    await broadcast_sensor_update(
        pond_id=webhook_data.pond_id,
        sensor_data=webhook_data.dict(),
        status=calculated_status,
        user_id=current_user.id
    )
    
    return db_sensor_data

@router.post("/bulk", response_model=SensorDataBulkResponse, status_code=status.HTTP_201_CREATED)
async def create_bulk_sensor_data(
    bulk_data: SensorDataBulk,
    current_user: dict = Depends(get_current_active_user),
):
    """
    Create multiple sensor data readings in bulk
    """
    batch_id = bulk_data.batch_id or f"batch_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    successful = 0
    failed = 0
    errors = []
    
    for reading in bulk_data.readings:
        try:
            # Verify pond access
            verify_sensor_data_access(reading.pond_id, current_user, db)
            
            # Calculate status
            calculated_status = calculate_sensor_status(reading.sensor_type, reading.value)
            
            # Create sensor reading
            db_sensor_data = SensorReading(
                pond_id=reading.pond_id,
                sensor_type=reading.sensor_type,
                value=reading.value,
                status=calculated_status,
                meta_data=reading.meta_data,
                timestamp=datetime.utcnow()
            )
            
            db.add(db_sensor_data)
            successful += 1
            
            # Broadcast update to WebSocket clients
            await broadcast_sensor_update(
                pond_id=reading.pond_id,
                sensor_data=reading.dict(),
                status=calculated_status,
                user_id=current_user.id
            )
            
        except Exception as e:
            failed += 1
            errors.append({
                "reading": reading.dict(),
                "error": str(e)
            })
    
    # Commit all successful readings
    if successful > 0:
        db.commit()
    
    logger.info(f"Bulk sensor data: {successful} successful, {failed} failed")
    
    return SensorDataBulkResponse(
        batch_id=batch_id,
        total_processed=len(bulk_data.readings),
        successful=successful,
        failed=failed,
        errors=errors
    )

@router.get("/ponds/{pond_id}/data", response_model=SensorDataList)
async def get_pond_sensor_data(
    pond_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Page size"),
    sensor_type: Optional[str] = Query(None, description="Filter by sensor type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    start_date: Optional[datetime] = Query(None, description="Start date for filtering"),
    end_date: Optional[datetime] = Query(None, description="End date for filtering"),
    current_user: dict = Depends(get_current_active_user),
):
    """
    Get all sensor data for a specific pond with pagination and filtering
    """
    # Verify pond access
    verify_sensor_data_access(pond_id, current_user, db)
    
    # Build query
    query = db.query(SensorReading).filter(SensorReading.pond_id == pond_id)
    
    # Apply filters
    if sensor_type:
        query = query.filter(SensorReading.sensor_type == sensor_type)
    
    if status:
        query = query.filter(SensorReading.status == status)
    
    if start_date:
        query = query.filter(SensorReading.timestamp >= start_date)
    
    if end_date:
        query = query.filter(SensorReading.timestamp <= end_date)
    
    # Get total count
    total = query.count()
    
    # Apply pagination and ordering
    offset = (page - 1) * size
    sensor_data = query.order_by(desc(SensorReading.timestamp)).offset(offset).limit(size).all()
    
    # Calculate total pages
    total_pages = (total + size - 1) // size
    
    return SensorDataList(
        sensor_data=sensor_data,
        total=total,
        page=page,
        size=size,
        total_pages=total_pages
    )

@router.get("/ponds/{pond_id}/latest", response_model=List[SensorDataLatest])
async def get_latest_sensor_readings(
    pond_id: int,
    current_user: dict = Depends(get_current_active_user),
):
    """
    Get latest sensor readings for all sensor types in a pond
    """
    # Verify pond access
    verify_sensor_data_access(pond_id, current_user, db)
    
    # Get all sensor types for this pond
    sensor_types = db.query(SensorReading.sensor_type).filter(
        SensorReading.pond_id == pond_id
    ).distinct().all()
    
    latest_readings = []
    
    for (sensor_type,) in sensor_types:
        # Get latest reading
        latest = db.query(SensorReading).filter(
            and_(
                SensorReading.pond_id == pond_id,
                SensorReading.sensor_type == sensor_type
            )
        ).order_by(desc(SensorReading.timestamp)).first()
        
        # Get previous reading for trend calculation
        previous = db.query(SensorReading).filter(
            and_(
                SensorReading.pond_id == pond_id,
                SensorReading.sensor_type == sensor_type,
                SensorReading.timestamp < latest.timestamp
            )
        ).order_by(desc(SensorReading.timestamp)).first()
        
        # Calculate trend
        trend = None
        if previous:
            if latest.value > previous.value:
                trend = "increasing"
            elif latest.value < previous.value:
                trend = "decreasing"
            else:
                trend = "stable"
        
        latest_readings.append(SensorDataLatest(
            pond_id=pond_id,
            sensor_type=sensor_type,
            latest_reading=latest,
            previous_reading=previous,
            trend=trend
        ))
    
    return latest_readings

@router.get("/ponds/{pond_id}/sensors/{sensor_type}", response_model=List[SensorDataResponse])
async def get_specific_sensor_data(
    pond_id: int,
    sensor_type: str,
    limit: int = Query(100, ge=1, le=1000, description="Number of readings to return"),
    current_user: dict = Depends(get_current_active_user),
):
    """
    Get sensor data for a specific sensor type in a pond
    """
    # Verify pond access
    verify_sensor_data_access(pond_id, current_user, db)
    
    sensor_data = db.query(SensorReading).filter(
        and_(
            SensorReading.pond_id == pond_id,
            SensorReading.sensor_type == sensor_type
        )
    ).order_by(desc(SensorReading.timestamp)).limit(limit).all()
    
    return sensor_data

@router.get("/ponds/{pond_id}/aggregation", response_model=List[SensorDataAggregation])
async def get_sensor_data_aggregation(
    pond_id: int,
    period: str = Query(..., description="Aggregation period (1h, 1d, 1w, 1m)"),
    sensor_type: Optional[str] = Query(None, description="Filter by sensor type"),
    current_user: dict = Depends(get_current_active_user),
):
    """
    Get aggregated sensor data for a pond over time periods
    """
    # Verify pond access
    verify_sensor_data_access(pond_id, current_user, db)
    
    # Calculate time period
    now = datetime.utcnow()
    if period == "1h":
        start_time = now - timedelta(hours=1)
    elif period == "1d":
        start_time = now - timedelta(days=1)
    elif period == "1w":
        start_time = now - timedelta(weeks=1)
    elif period == "1m":
        start_time = now - timedelta(days=30)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid period. Use: 1h, 1d, 1w, 1m"
        )
    
    # Build query
    query = db.query(SensorReading).filter(
        and_(
            SensorReading.pond_id == pond_id,
            SensorReading.timestamp >= start_time
        )
    )
    
    if sensor_type:
        query = query.filter(SensorReading.sensor_type == sensor_type)
    
    # Get all readings for aggregation
    readings = query.all()
    
    # Group by sensor type and calculate aggregates
    aggregation_results = []
    sensor_groups = {}
    
    for reading in readings:
        if reading.sensor_type not in sensor_groups:
            sensor_groups[reading.sensor_type] = []
        sensor_groups[reading.sensor_type].append(reading)
    
    for sensor_type, sensor_readings in sensor_groups.items():
        values = [r.value for r in sensor_readings]
        status_counts = {
            'green': len([r for r in sensor_readings if r.status == 'green']),
            'yellow': len([r for r in sensor_readings if r.status == 'yellow']),
            'red': len([r for r in sensor_readings if r.status == 'red'])
        }
        
        aggregation_results.append(SensorDataAggregation(
            sensor_type=sensor_type,
            pond_id=pond_id,
            period=period,
            min_value=min(values),
            max_value=max(values),
            avg_value=sum(values) / len(values),
            count=len(values),
            green_count=status_counts['green'],
            yellow_count=status_counts['yellow'],
            red_count=status_counts['red'],
            start_time=start_time,
            end_time=now
        ))
    
    return aggregation_results

@router.get("/admin/thresholds", response_model=List[SensorThresholdResponse])
async def get_sensor_thresholds(
    current_user: dict = Depends(get_admin_user),
):
    """
    Get all sensor thresholds (admin only)
    """
    # This would typically query a thresholds table
    # For now, return default thresholds
    default_thresholds = [
        SensorThresholdResponse(
            id=1,
            sensor_type="temperature",
            yellow_min=25.0,
            yellow_max=32.0,
            red_min=0.0,
            red_max=100.0,
            unit="°C",
            description="Water temperature thresholds",
            created_at=datetime.utcnow()
        ),
        SensorThresholdResponse(
            id=2,
            sensor_type="oxygen",
            yellow_min=3.0,
            yellow_max=5.0,
            red_min=0.0,
            red_max=2.9,
            unit="mg/L",
            description="Dissolved oxygen thresholds",
            created_at=datetime.utcnow()
        )
    ]
    
    return default_thresholds
