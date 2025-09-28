"""
Sensor data management endpoints for Backend_PWA
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from datetime import datetime, timedelta
import logging
import json
from pydantic import BaseModel

from ...storage import SensorReadingStorage, SensorBatchStorage, YorrKungStorage, PondStorage
from ...storage.graph_storage import GraphDataStorage
from ...storage.shrimp_size_storage import ShrimpSizeStorage
from ...storage.routine_storage import RoutineStorage
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
from ...schemas.graph import GraphDataResponse, GraphDataPoint, MultiSensorGraphResponse
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
        },
        'DO': {
            'yellow': [(3, 5)],
            'red': [(0, 2.9)]
        },
        'minerals': {
            'yellow': [(50, 100)],  # Low mineral levels
            'red': [(0, 49)]  # Very low mineral levels
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

# New endpoint for receiving bulk sensor data in batch format (RECOMMENDED)
@router.post("/batch-sensor-data", response_model=dict, status_code=status.HTTP_201_CREATED)
async def receive_batch_sensor_data(
    request_data: dict,
):
    """
    Receive batch sensor data in optimized format:
    {
      "pondId": "1",
      "timestamp": "2024-01-01T12:00:00.000Z",
      "DO": 0,
      "PH": 10,
      "Temp": 0,
      "ColorWater": "red",
      "Mineral_1": 4800,
      "Mineral_2": 4800,
      "Mineral_3": 150.5,
      "Mineral_4": 200.0,
      "PicColorWater": "https://exampleUrl.com",
      "PicKungOnWater": "https://exampleUrl.com"
    }
    
    This stores all sensor data as a single batch record for better performance.
    """
    try:
        # Extract data from request
        pond_id = request_data.get("pondId", "1")
        timestamp = request_data.get("timestamp")
        
        # Convert pond_id to int if it's a string
        try:
            pond_id = int(pond_id)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="pondId must be a valid integer"
            )
        
        # Parse timestamp if provided
        if timestamp:
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                # Ensure timezone-naive for consistent processing
                if timestamp.tzinfo is not None:
                    timestamp = timestamp.replace(tzinfo=None)
            except ValueError:
                timestamp = datetime.utcnow()
        else:
            timestamp = datetime.utcnow()
        
        # Generate batch ID
        batch_id = f"batch_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}"
        
        # Map keys to sensor types
        sensor_mapping = {
            'DO': 'DO',
            'PH': 'pH', 
            'Temp': 'temperature',
            # 'Size': 'shrimpSize',  # Removed - ShrimpSize now handled separately
            'Mineral': 'minerals',
            'Mineral_1': 'minerals_1',
            'Mineral_2': 'minerals_2',
            'Mineral_3': 'minerals_3',
            'Mineral_4': 'minerals_4',
            'ColorWater': 'waterColor',  # ColorWater with status (green/yellow/red)
            'SizePic': 'sizePicture',
            'PicFood': 'foodPicture', 
            'PicColorWater': 'waterColorPicture',  # PicColorWater with URL
            'PicKungOnWater': 'kungOnWaterPicture'  # PicKungOnWater with URL
        }
        
        # Process sensor data - support both old and new formats
        sensors_data = {}
        
        # Check if this is new format (with sensors array)
        if 'sensors' in request_data and isinstance(request_data['sensors'], list):
            # New format: {"pond_id": 1, "sensors": [{"sensor_type": "temperature", "value": 25.5, "status": "green"}]}
            for sensor in request_data['sensors']:
                sensor_type = sensor.get('sensor_type')
                value = sensor.get('value')
                status = sensor.get('status', 'info')
                
                if sensor_type and value is not None:
                    # Determine type based on value
                    if isinstance(value, str) and (value.startswith('http') or value.startswith('https')):
                        value_type = 'url'
                    elif isinstance(value, (int, float)):
                        value_type = 'numeric'
                    else:
                        value_type = 'string'
                    
                    sensors_data[sensor_type] = {
                        'value': value,
                        'type': value_type,
                        'status': status
                    }
        else:
            # Old format: {"pondId": "1", "DO": 9.8, "PH": 7.5, ...}
            for key, value in request_data.items():
                if key in ['pondId', 'timestamp']:
                    continue  # Skip metadata fields
                    
                if key in sensor_mapping:
                    sensor_type = sensor_mapping[key]
                    
                    # Handle different value types
                    if key in ['SizePic', 'PicFood', 'PicColorWater', 'PicKungOnWater']:
                        # These are URLs
                        sensors_data[sensor_type] = {
                            'value': str(value),
                            'type': 'url',
                            'status': 'info'
                        }
                    elif key == 'ColorWater':
                        # ColorWater with status (green/yellow/red)
                        sensors_data[sensor_type] = {
                            'value': str(value),
                            'type': 'status',
                            'status': str(value)  # Use the value as status
                        }
                    else:
                        # Handle Mineral_1-4 fields differently
                        if sensor_type.startswith('minerals_'):
                            # Mineral_3-4: float values (weight in grams) - check first
                            if sensor_type in ['minerals_3', 'minerals_4']:
                                logger.info(f"Processing {sensor_type} with value: {value}")
                                try:
                                    numeric_value = float(value)
                                    calculated_status = calculate_sensor_status('minerals', numeric_value)
                                    sensors_data[sensor_type] = {
                                        'value': numeric_value,
                                        'type': 'numeric',
                                        'status': calculated_status
                                    }
                                    logger.info(f"Result for {sensor_type}: {sensors_data[sensor_type]}")
                                except (ValueError, TypeError):
                                    # If not numeric, store as string with default status
                                    sensors_data[sensor_type] = {
                                        'value': str(value),
                                        'type': 'string',
                                        'status': 'info'
                                    }
                                    logger.info(f"Result for {sensor_type} (string): {sensors_data[sensor_type]}")
                            # Mineral_1-2: numeric values (weight in grams)
                            elif sensor_type in ['minerals_1', 'minerals_2']:
                                try:
                                    numeric_value = float(value)
                                    calculated_status = calculate_sensor_status('minerals', numeric_value)
                                    sensors_data[sensor_type] = {
                                        'value': numeric_value,
                                        'type': 'numeric',
                                        'status': calculated_status
                                    }
                                except (ValueError, TypeError):
                                    # If not numeric, store as string
                                    sensors_data[sensor_type] = {
                                        'value': str(value),
                                        'type': 'string',
                                        'status': 'info'
                                    }
                            # Other minerals (fallback)
                            else:
                                try:
                                    numeric_value = float(value)
                                    calculated_status = calculate_sensor_status('minerals', numeric_value)
                                    sensors_data[sensor_type] = {
                                        'value': numeric_value,
                                        'type': 'numeric',
                                        'status': calculated_status
                                    }
                                except (ValueError, TypeError):
                                    sensors_data[sensor_type] = {
                                        'value': str(value),
                                        'type': 'string',
                                        'status': 'info'
                                    }
                        else:
                            # Other numeric values
                            try:
                                numeric_value = float(value)
                                calculated_status = calculate_sensor_status(sensor_type, numeric_value)
                                sensors_data[sensor_type] = {
                                    'value': numeric_value,
                                    'type': 'numeric',
                                    'status': calculated_status
                                }
                            except (ValueError, TypeError):
                                # If not numeric, store as string
                                sensors_data[sensor_type] = {
                                    'value': str(value),
                                    'type': 'status',
                                    'status': 'yellow' if str(value).lower() == 'true' else 'green'
                                }
        
        # Create batch record
        batch_data = {
            "id": batch_id,
            "pond_id": pond_id,
            "timestamp": timestamp.isoformat(),
            "sensors": sensors_data,
            "created_at": datetime.utcnow().isoformat(),
            "source": "batch_api"
        }
        
        # Store in batch storage
        batch_storage = SensorBatchStorage()
        stored_batch = batch_storage.create(batch_data)
        
        # Also store in graph_data.json for graph visualization
        # Only store DO, pH, and temperature sensors
        graph_sensors = {}
        for sensor_type in ['DO', 'pH', 'temperature']:
            if sensor_type in sensors_data:
                graph_sensors[sensor_type] = sensors_data[sensor_type]
        
        if graph_sensors:  # Only create graph entry if we have graph sensors
            graph_data = {
                "id": f"graph_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}",
                "pond_id": pond_id,
                "timestamp": timestamp.isoformat(),
                "sensors": graph_sensors
            }
            
            # Store in graph data storage
            graph_storage = GraphDataStorage()
            graph_storage.create(graph_data)
            
            logger.info(f"Stored graph data for batch {batch_id} with {len(graph_sensors)} graph sensors for pond {pond_id}")
        
        # Store ShrimpSize data separately for graph visualization
        if 'shrimpSize' in sensors_data:
            shrimp_size_value = sensors_data['shrimpSize'].get('value', 0.0)
            if isinstance(shrimp_size_value, (int, float)) and shrimp_size_value > 0:
                shrimp_size_data = {
                    "id": f"shrimp_size_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}",
                    "pond_id": pond_id,
                    "timestamp": timestamp.isoformat(),
                    "shrimp_size": float(shrimp_size_value)
                }
                
                # Store in shrimp size storage
                shrimp_size_storage = ShrimpSizeStorage()
                shrimp_size_storage.create(shrimp_size_data)
                
                logger.info(f"Stored shrimp size data for batch {batch_id}: {shrimp_size_value}cm for pond {pond_id}")
        
        logger.info(f"Stored batch {batch_id} with {len(sensors_data)} sensors for pond {pond_id}")
        
        # Send push notifications for sensor alerts
        try:
            from ...core.notification_triggers import notification_triggers
            from ...storage import PondStorage
            
            # Get pond owner for notifications
            pond_storage = PondStorage()
            pond = pond_storage.get_by_id(pond_id)
            
            if pond and pond.get('owner_id'):
                # Check for sensor alerts
                await notification_triggers.check_sensor_alerts(
                    pond_id=str(pond_id),
                    sensor_data=sensors_data,
                    user_id=pond['owner_id']
                )
                
                logger.info(f"Checked sensor alerts for pond {pond_id}")
        except Exception as e:
            logger.error(f"Error checking sensor alerts: {e}")
            # Don't fail the main request if notifications fail
        
        # Return success response
        return {
            "success": True,
            "message": f"Batch sensor data received successfully ({len(sensors_data)} sensors)",
            "data": {
                "batchId": batch_id,
                "pondId": pond_id,
                "timestamp": timestamp.isoformat(),
                "sensors": sensors_data,
                "stored_batch": stored_batch
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing batch sensor data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process batch sensor data: {str(e)}"
        )

# New endpoint for receiving shrimp size data (YorrKung)
@router.post("/batch-yorrkung-data", response_model=dict, status_code=status.HTTP_201_CREATED)
async def receive_batch_yorrkung_data(
    request_data: dict,
):
    """
    Receive batch shrimp size data in optimized format:
    {
      "pondId": "1",
      "timestamp": "2024-01-01T12:00:00.000Z",
      "Size_CM": 10,
      "Size_gram": 100,
      "SizePic": "https://exampleUrl.com",
      "PicFood": "https://exampleUrl.com",
      "PicKungDin": "https://exampleUrl.com"
    }
    
    This stores all shrimp size data as a single batch record for better performance.
    """
    try:
        # Extract data from request
        pond_id = request_data.get("pondId", "1")
        timestamp = request_data.get("timestamp")
        
        # Convert pond_id to int if it's a string
        try:
            pond_id = int(pond_id)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="pondId must be a valid integer"
            )
        
        # Parse timestamp if provided
        if timestamp:
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                # Ensure timezone-naive for consistent processing
                if timestamp.tzinfo is not None:
                    timestamp = timestamp.replace(tzinfo=None)
            except ValueError:
                timestamp = datetime.utcnow()
        else:
            timestamp = datetime.utcnow()
        
        # Generate batch ID
        batch_id = f"yorrkung_batch_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}"
        
        # Map keys to sensor types for YorrKung data
        yorrkung_sensor_mapping = {
            'Size_CM': 'size_cm',
            'Size_gram': 'size_gram',
            'SizePic': 'sizePicture',
            'PicFood': 'foodPicture',
            'PicKungDin': 'kungDinPicture'
        }
        
        # Process sensor data
        sensors_data = {}
        
        for key, value in request_data.items():
            if key in ['pondId', 'timestamp']:
                continue  # Skip metadata fields
                
            if key in yorrkung_sensor_mapping:
                sensor_type = yorrkung_sensor_mapping[key]
                
                # Handle different value types
                if key in ['SizePic', 'PicFood', 'PicKungDin']:
                    # These are URLs
                    sensors_data[sensor_type] = {
                        'value': str(value),
                        'type': 'url',
                        'status': 'info'
                    }
                else:
                    # These are numeric values (Size_CM, Size_gram)
                    try:
                        numeric_value = float(value)
                        # Calculate status based on reasonable thresholds for shrimp size
                        calculated_status = 'green'  # Default to green for shrimp size data
                        if sensor_type == 'size_cm':
                            # Shrimp size in CM - reasonable range 1-15 cm
                            if numeric_value < 1 or numeric_value > 15:
                                calculated_status = 'yellow'
                        elif sensor_type == 'size_gram':
                            # Shrimp weight in grams - reasonable range 1-200 grams
                            if numeric_value < 1 or numeric_value > 200:
                                calculated_status = 'yellow'
                        
                        sensors_data[sensor_type] = {
                            'value': numeric_value,
                            'type': 'numeric',
                            'status': calculated_status
                        }
                    except (ValueError, TypeError):
                        # If not numeric, store as string
                        sensors_data[sensor_type] = {
                            'value': str(value),
                            'type': 'string',
                            'status': 'info'
                        }
        
        # Create batch record
        batch_data = {
            "id": batch_id,
            "pond_id": pond_id,
            "timestamp": timestamp.isoformat(),
            "sensors": sensors_data,
            "created_at": datetime.utcnow().isoformat(),
            "source": "yorrkung_batch_api"
        }
        
        # Store in YorrKung batch storage
        yorrkung_storage = YorrKungStorage()
        stored_batch = yorrkung_storage.create(batch_data)
        
        logger.info(f"Stored YorrKung batch {batch_id} with {len(sensors_data)} sensors for pond {pond_id}")
        
        # Return success response
        return {
            "success": True,
            "message": f"YorrKung batch data received successfully ({len(sensors_data)} sensors)",
            "data": {
                "batchId": batch_id,
                "pondId": pond_id,
                "timestamp": timestamp.isoformat(),
                "sensors": sensors_data,
                "stored_batch": stored_batch
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing YorrKung batch data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process YorrKung batch data: {str(e)}"
        )

# New endpoint for getting batch history
@router.get("/batches/{pond_id}", response_model=dict)
async def get_sensor_batch_history(
    pond_id: int,
    limit: int = Query(10, ge=1, le=100, description="Number of batches to return")
):
    """
    Get sensor batch history for a specific pond
    """
    try:
        # Convert pond_id to int if it's a string
        try:
            pond_id = int(pond_id)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="pondId must be a valid integer"
            )
        
        # Get batch history
        batch_storage = SensorBatchStorage()
        batches = batch_storage.get_batch_history(pond_id, limit)
        
        return {
            "success": True,
            "data": {
                "pondId": pond_id,
                "batches": batches,
                "count": len(batches)
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting sensor batch history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sensor batch history: {str(e)}"
        )

# New endpoint for getting latest YorrKung batch data (single batch)
@router.get("/yorrkung-batches/{pond_id}", response_model=dict)
async def get_latest_yorrkung_batch_data(
    pond_id: int,
):
    """
    Get latest YorrKung batch data for a specific pond (single batch only)
    """
    try:
        # Convert pond_id to int if it's a string
        try:
            pond_id = int(pond_id)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="pondId must be a valid integer"
            )
        
        # Get latest YorrKung batch data
        yorrkung_storage = YorrKungStorage()
        latest_batch = yorrkung_storage.get_latest_batch(pond_id)
        
        if not latest_batch:
            return {
                "success": True,
                "data": {
                    "pondId": pond_id,
                    "batches": [],
                    "count": 0,
                    "message": "No YorrKung data found for this pond"
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Return single batch in the same format as before
        return {
            "success": True,
            "data": {
                "pondId": pond_id,
                "batches": [latest_batch],  # Wrap in array to maintain compatibility
                "count": 1
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting latest YorrKung batch data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get latest YorrKung batch data: {str(e)}"
        )

# Single sensor endpoint removed - use batch-sensor-data instead

# Webhook endpoint removed - use batch-sensor-data instead

# Bulk endpoint removed - use batch-sensor-data instead

# Single sensor data endpoint removed - use batch endpoints instead

# Single sensor latest endpoint removed - use batch endpoints instead

# Specific sensor data endpoint removed - use batch endpoints instead

# Aggregation endpoint removed - use batch endpoints instead

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

# Add endpoint for latest YorrKung data
@router.get("/yorrkung-latest/{pond_id}", response_model=dict)
async def get_latest_yorrkung_data(
    pond_id: int,
    current_user: dict = Depends(get_current_active_user),
):
    """
    Get latest YorrKung data for a specific pond (authenticated)
    """
    try:
        # Convert pond_id to int if it's a string
        try:
            pond_id = int(pond_id)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="pondId must be a valid integer"
            )
        
        # Verify pond access
        verify_sensor_data_access(pond_id, current_user)
        
        # Use YorrKungStorage to get latest batch data
        yorrkung_storage = YorrKungStorage()
        
        # Get the latest batch for this pond (without removing it)
        latest_batch = yorrkung_storage.get_latest_batch(pond_id)
        
        if not latest_batch:
            return {
                "success": True,
                "data": {
                    "pondId": pond_id,
                    "sensors": {},
                    "timestamp": datetime.utcnow().isoformat(),
                    "message": "No YorrKung data found for this pond"
                }
            }
        
        # Debug logging
        logger.info(f"Latest YorrKung batch (authenticated): {latest_batch}")
        
        # Extract sensors data from the latest batch
        sensors_data = latest_batch.get("sensors", {})
        
        # Debug logging
        logger.info(f"YorrKung sensors data (authenticated): {sensors_data}")
        
        # Convert batch format to latest format
        latest_data = {}
        for sensor_type, sensor_info in sensors_data.items():
            if isinstance(sensor_info, dict):
                latest_data[sensor_type] = {
                    "value": sensor_info.get("value"),
                    "timestamp": latest_batch.get("timestamp"),
                    "status": sensor_info.get("status", "unknown")
                }
            else:
                # Handle simple value format
                latest_data[sensor_type] = {
                    "value": sensor_info,
                    "timestamp": latest_batch.get("timestamp"),
                    "status": "unknown"
                }
        
        return {
            "success": True,
            "data": {
                "pondId": pond_id,
                "sensors": latest_data,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting latest YorrKung data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get latest YorrKung data: {str(e)}"
        )

# Add endpoint for /sensors/latest/{pond_id} to match client expectations
@router.get("/latest/{pond_id}", response_model=dict)
async def get_latest_sensor_data_simple(
    pond_id: int,
    current_user: dict = Depends(get_current_active_user),
):
    """
    Get latest sensor readings for a specific pond (simple format)
    This endpoint matches the client's expected URL pattern
    """
    try:
        # Convert pond_id to int if it's a string
        try:
            pond_id = int(pond_id)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="pondId must be a valid integer"
            )
        
        # Verify pond access
        verify_sensor_data_access(pond_id, current_user)
        
        # Use SensorBatchStorage to get latest batch data
        batch_storage = SensorBatchStorage()
        
        # Get the latest batch for this pond (without removing it)
        latest_batch = batch_storage.get_latest_batch(pond_id)
        
        if not latest_batch:
            return {
                "success": True,
                "data": {
                    "pondId": pond_id,
                    "sensors": {},
                    "timestamp": datetime.utcnow().isoformat(),
                    "message": "No sensor data found for this pond"
                }
            }
        
        # Debug logging
        logger.info(f"Latest batch (authenticated): {latest_batch}")
        
        # Extract sensors data from the latest batch
        sensors_data = latest_batch.get("sensors", {})
        
        # Debug logging
        logger.info(f"Sensors data (authenticated): {sensors_data}")
        
        # Convert batch format to latest format
        latest_data = {}
        for sensor_type, sensor_info in sensors_data.items():
            if isinstance(sensor_info, dict):
                latest_data[sensor_type] = {
                    "value": sensor_info.get("value"),
                    "timestamp": latest_batch.get("timestamp"),
                    "status": sensor_info.get("status", "unknown")
                }
            else:
                # Handle simple value format
                latest_data[sensor_type] = {
                    "value": sensor_info,
                    "timestamp": latest_batch.get("timestamp"),
                    "status": "unknown"
                }
        
        return {
            "success": True,
            "data": {
                "pondId": pond_id,
                "sensors": latest_data,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting latest sensor data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get latest sensor data: {str(e)}"
        )

# Add endpoint without authentication for testing
@router.get("/latest/{pond_id}/public", response_model=dict)
async def get_latest_sensor_data_public(pond_id: int):
    """
    Get latest sensor readings for a specific pond (public access for testing)
    """
    try:
        # Convert pond_id to int if it's a string
        try:
            pond_id = int(pond_id)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="pondId must be a valid integer"
            )
        
        # Use SensorBatchStorage to get latest batch data
        batch_storage = SensorBatchStorage()
        
        # Get the latest batch for this pond (without removing it)
        latest_batch = batch_storage.get_latest_batch(pond_id)
        
        if not latest_batch:
            return {
                "success": True,
                "data": {
                    "pondId": pond_id,
                    "sensors": {},
                    "timestamp": datetime.utcnow().isoformat(),
                    "message": "No sensor data found for this pond"
                }
            }
        
        # Debug logging
        logger.info(f"Latest batch: {latest_batch}")
        
        # Extract sensors data from the latest batch
        sensors_data = latest_batch.get("sensors", {})
        
        # Debug logging
        logger.info(f"Sensors data: {sensors_data}")
        
        # Convert batch format to latest format
        latest_data = {}
        for sensor_type, sensor_info in sensors_data.items():
            if isinstance(sensor_info, dict):
                latest_data[sensor_type] = {
                    "value": sensor_info.get("value"),
                    "timestamp": latest_batch.get("timestamp"),
                    "status": sensor_info.get("status", "unknown")
                }
            else:
                # Handle simple value format
                latest_data[sensor_type] = {
                    "value": sensor_info,
                    "timestamp": latest_batch.get("timestamp"),
                    "status": "unknown"
                }
        
        return {
            "success": True,
            "data": {
                "pondId": pond_id,
                "sensors": latest_data,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting latest sensor data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get latest sensor data: {str(e)}"
        )

# Admin endpoint to clear all sensor batch data
@router.delete("/admin/clear-all-batches", response_model=dict)
async def clear_all_sensor_batches(
    current_user: dict = Depends(get_admin_user),
):
    """
    Clear all sensor batch data (admin only)
    """
    try:
        # Clear all batch data
        batch_storage = SensorBatchStorage()
        success = batch_storage.clear_all()
        
        if success:
            logger.info(f"All sensor batch data cleared by admin user {current_user['id']}")
            return {
                "success": True,
                "message": "All sensor batch data cleared successfully",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to clear sensor batch data"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to clear sensor batch data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear sensor batch data"
        )

# Admin endpoint to clear sensor batch data for a specific pond
@router.delete("/admin/clear-batches/{pond_id}", response_model=dict)
async def clear_sensor_batches_for_pond(
    pond_id: int,
    current_user: dict = Depends(get_admin_user),
):
    """
    Clear sensor batch data for a specific pond (admin only)
    """
    try:
        # Convert pond_id to int if it's a string
        try:
            pond_id = int(pond_id)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="pondId must be a valid integer"
            )
        
        # Clear batch data for specific pond
        batch_storage = SensorBatchStorage()
        success = batch_storage.clear_by_pond(pond_id)
        
        if success:
            logger.info(f"Sensor batch data for pond {pond_id} cleared by admin user {current_user['id']}")
            return {
                "success": True,
                "message": f"Sensor batch data for pond {pond_id} cleared successfully",
                "pondId": pond_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to clear sensor batch data for pond"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to clear sensor batch data for pond {pond_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear sensor batch data for pond"
        )

# Admin endpoint to clear all YorrKung batch data
@router.delete("/admin/clear-all-yorrkung-batches", response_model=dict)
async def clear_all_yorrkung_batches(
    current_user: dict = Depends(get_admin_user),
):
    """
    Clear all YorrKung batch data (admin only)
    """
    try:
        # Clear all YorrKung batch data
        yorrkung_storage = YorrKungStorage()
        success = yorrkung_storage.clear_all()
        
        if success:
            logger.info(f"All YorrKung batch data cleared by admin user {current_user['id']}")
            return {
                "success": True,
                "message": "All YorrKung batch data cleared successfully",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to clear YorrKung batch data"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to clear YorrKung batch data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear YorrKung batch data"
        )

# Admin endpoint to clear YorrKung batch data for a specific pond
@router.delete("/admin/clear-yorrkung-batches/{pond_id}", response_model=dict)
async def clear_yorrkung_batches_for_pond(
    pond_id: int,
    current_user: dict = Depends(get_admin_user),
):
    """
    Clear YorrKung batch data for a specific pond (admin only)
    """
    try:
        # Convert pond_id to int if it's a string
        try:
            pond_id = int(pond_id)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="pondId must be a valid integer"
            )
        
        # Clear YorrKung batch data for specific pond
        yorrkung_storage = YorrKungStorage()
        success = yorrkung_storage.clear_by_pond(pond_id)
        
        if success:
            logger.info(f"YorrKung batch data for pond {pond_id} cleared by admin user {current_user['id']}")
            return {
                "success": True,
                "message": f"YorrKung batch data for pond {pond_id} cleared successfully",
                "pondId": pond_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to clear YorrKung batch data for pond"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to clear YorrKung batch data for pond {pond_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear YorrKung batch data for pond"
        )

# Endpoint to delete the latest batch for a specific pond
@router.delete("/batches/{pond_id}/latest", response_model=dict)
async def delete_latest_sensor_batch(
    pond_id: int,
    current_user: dict = Depends(get_current_active_user),
):
    """
    Delete the latest sensor batch for a specific pond
    """
    try:
        # Convert pond_id to int if it's a string
        try:
            pond_id = int(pond_id)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="pondId must be a valid integer"
            )
        
        # Verify pond access
        verify_sensor_data_access(pond_id, current_user)
        
        # Delete latest batch for this pond
        batch_storage = SensorBatchStorage()
        deleted_batch = batch_storage.delete_latest_batch(pond_id)
        
        if deleted_batch:
            logger.info(f"Latest sensor batch for pond {pond_id} deleted by user {current_user['id']}")
            return {
                "success": True,
                "message": f"Latest sensor batch for pond {pond_id} deleted successfully",
                "deletedBatch": deleted_batch,
                "pondId": pond_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            return {
                "success": False,
                "message": f"No sensor batch data found for pond {pond_id}",
                "pondId": pond_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete latest sensor batch for pond {pond_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete latest sensor batch"
        )

# Endpoint to delete the latest YorrKung batch for a specific pond
@router.delete("/yorrkung-batches/{pond_id}/latest", response_model=dict)
async def delete_latest_yorrkung_batch(
    pond_id: int,
    current_user: dict = Depends(get_current_active_user),
):
    """
    Delete the latest YorrKung batch for a specific pond
    """
    try:
        # Convert pond_id to int if it's a string
        try:
            pond_id = int(pond_id)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="pondId must be a valid integer"
            )
        
        # Verify pond access
        verify_sensor_data_access(pond_id, current_user)
        
        # Delete latest YorrKung batch for this pond
        yorrkung_storage = YorrKungStorage()
        deleted_batch = yorrkung_storage.delete_latest_batch(pond_id)
        
        if deleted_batch:
            logger.info(f"Latest YorrKung batch for pond {pond_id} deleted by user {current_user['id']}")
            return {
                "success": True,
                "message": f"Latest YorrKung batch for pond {pond_id} deleted successfully",
                "deletedBatch": deleted_batch,
                "pondId": pond_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            return {
                "success": False,
                "message": f"No YorrKung batch data found for pond {pond_id}",
                "pondId": pond_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete latest YorrKung batch for pond {pond_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete latest YorrKung batch"
        )

# Simple graph endpoint for testing
@router.get("/graph-simple/{pond_id}", response_model=dict)
async def get_sensor_graph_data_simple(
    pond_id: int, 
    hours: int = Query(24, ge=1, le=720, description="Number of hours to fetch data for"),
    timeframe: str = Query("1D", description="Timeframe: 1D, 7D, or 30D"),
    sensor_types: str = Query(None, description="Comma-separated list of sensor types to include (e.g., 'DO,pH,temperature')")
):
    """
    Get sensor data formatted for graph visualization (simple version)
    Supports timeframe parameter for better UX
    """
    try:
        # Get graph data using GraphDataStorage
        graph_storage = GraphDataStorage()
        batches = graph_storage.get_by_pond(pond_id)
        
        # Debug logging
        logging.info(f"API: Found {len(batches)} batches for pond {pond_id}")
        if batches:
            logging.info(f"API: First batch keys: {list(batches[0].keys())}")
            logging.info(f"API: First batch sensors: {list(batches[0].get('sensors', {}).keys())}")
            # Debug: Check actual sensor values
            for sensor_type in ['DO', 'pH', 'temperature', 'minerals']:
                if sensor_type in batches[0].get('sensors', {}):
                    sensor_data = batches[0]['sensors'][sensor_type]
                    logging.info(f"API: {sensor_type} data: {sensor_data}")
                else:
                    logging.info(f"API: {sensor_type} not found in sensors")
        
        # Filter data by timeframe based on hours parameter
        if batches:
            # Sort by timestamp to ensure correct filtering
            def batch_sort_key(x):
                timestamp = datetime.fromisoformat(x['timestamp'].replace('Z', '+00:00'))
                # Ensure timezone-naive for consistent sorting
                if timestamp.tzinfo is not None:
                    timestamp = timestamp.replace(tzinfo=None)
                return timestamp
            batches.sort(key=batch_sort_key)
            
            # Filter by time range based on timeframe
            end_time = datetime.now().replace(tzinfo=None)  # Make timezone-naive
            
            # Adjust time range based on timeframe
            if timeframe == "1D":
                # For 1D, show only today (00:00 to 23:59:59)
                start_time = end_time.replace(hour=0, minute=0, second=0, microsecond=0)
                end_time = end_time.replace(hour=23, minute=59, second=59, microsecond=999999)
            elif timeframe == "7D":
                # For 7D, show last 7 days with 4-hour intervals
                start_time = end_time - timedelta(days=7)
            elif timeframe == "30D":
                # For 30D, show last 30 days with 8-hour intervals
                start_time = end_time - timedelta(days=30)
            else:
                # Default to hours-based filtering
                start_time = end_time - timedelta(hours=hours)
            
            filtered_batches = []
            for batch in batches:
                try:
                    batch_time = datetime.fromisoformat(batch['timestamp'].replace('Z', '+00:00'))
                    # Ensure timezone-naive for comparison
                    if batch_time.tzinfo is not None:
                        batch_time_naive = batch_time.replace(tzinfo=None)
                    else:
                        batch_time_naive = batch_time
                    
                    # For 1D timeframe, ensure we only get today's data
                    if timeframe == "1D":
                        batch_date = batch_time_naive.date()
                        today_date = end_time.date()
                        if batch_date == today_date:
                            filtered_batches.append(batch)
                    else:
                        if start_time <= batch_time_naive <= end_time:
                            filtered_batches.append(batch)
                except Exception as e:
                    logging.warning(f"Error parsing timestamp {batch.get('timestamp')}: {e}")
                    continue
            
            # Further filter for 7D and 30D to reduce data points
            if timeframe == "7D":
                # Keep only every 4th hour for 7D, but ensure we include the latest data
                if len(filtered_batches) > 0:
                    # Always include the last batch (most recent data)
                    last_batch = filtered_batches[-1]
                    # Filter every 4th batch, but keep the last one
                    filtered_batches = [batch for i, batch in enumerate(filtered_batches[:-1]) if i % 4 == 0] + [last_batch]
            elif timeframe == "30D":
                # Keep only every 8th hour for 30D, but ensure we include the latest data
                if len(filtered_batches) > 0:
                    # Always include the last batch (most recent data)
                    last_batch = filtered_batches[-1]
                    # Filter every 8th batch, but keep the last one
                    filtered_batches = [batch for i, batch in enumerate(filtered_batches[:-1]) if i % 8 == 0] + [last_batch]
            
            batches = filtered_batches
            logging.info(f"API: Filtered to {len(batches)} batches for timeframe {timeframe}")
        
        # Process data for each sensor type
        sensors_data = {}
        numeric_sensors = ['DO', 'pH', 'temperature', 'minerals', 'shrimpSize']  # Added shrimpSize back
        
        # Parse requested sensor types
        requested_sensors = []
        if sensor_types:
            requested_sensors = [s.strip() for s in sensor_types.split(',') if s.strip()]
            # Filter to only include valid sensor types
            logging.info(f"DEBUG: Before filtering - requested_sensors: {requested_sensors}")
            logging.info(f"DEBUG: numeric_sensors: {numeric_sensors}")
            logging.info(f"DEBUG: 'shrimpSize' in requested_sensors: {'shrimpSize' in requested_sensors}")
            logging.info(f"DEBUG: 'shrimpSize' in numeric_sensors: {'shrimpSize' in numeric_sensors}")
            logging.info(f"DEBUG: 'shrimpSize' == 'shrimpSize': {'shrimpSize' == 'shrimpSize'}")
            logging.info(f"DEBUG: 'shrimpSize' in ['DO', 'pH', 'temperature', 'minerals', 'shrimpSize']: {'shrimpSize' in ['DO', 'pH', 'temperature', 'minerals', 'shrimpSize']}")
            logging.info(f"DEBUG: 'shrimpSize' in requested_sensors: {'shrimpSize' in requested_sensors}")
            logging.info(f"DEBUG: 'shrimpSize' in numeric_sensors: {'shrimpSize' in numeric_sensors}")
            logging.info(f"DEBUG: 'shrimpSize' in requested_sensors: {'shrimpSize' in requested_sensors}")
            logging.info(f"DEBUG: 'shrimpSize' in numeric_sensors: {'shrimpSize' in numeric_sensors}")
            logging.info(f"DEBUG: 'shrimpSize' in requested_sensors: {'shrimpSize' in requested_sensors}")
            logging.info(f"DEBUG: 'shrimpSize' in numeric_sensors: {'shrimpSize' in numeric_sensors}")
            requested_sensors = [s for s in requested_sensors if s in numeric_sensors]
            logging.info(f"DEBUG: After filtering - requested_sensors: {requested_sensors}")
            logging.info(f"Parsed sensor_types parameter: '{sensor_types}' -> {requested_sensors}")
        else:
            # If no sensor_types specified, return all
            requested_sensors = numeric_sensors
            logging.info(f"No sensor_types specified, returning all: {requested_sensors}")
        
        logging.info(f"Final requested sensor types: {requested_sensors}")
        logging.info(f"DEBUG: numeric_sensors: {numeric_sensors}")
        logging.info(f"DEBUG: 'shrimpSize' in numeric_sensors: {'shrimpSize' in numeric_sensors}")
        logging.info(f"DEBUG: 'shrimpSize' == 'shrimpSize': {'shrimpSize' == 'shrimpSize'}")
        logging.info(f"DEBUG: 'shrimpSize' in ['DO', 'pH', 'temperature', 'minerals', 'shrimpSize']: {'shrimpSize' in ['DO', 'pH', 'temperature', 'minerals', 'shrimpSize']}")
        
        # Filter out any unwanted sensor types from batches
        for batch in batches:
            if 'sensors' in batch:
                # Remove unwanted sensor types (but keep shrimpSize)
                unwanted_sensors = ['size', 'Size']  # Keep shrimpSize, shrimpsize
                for unwanted in unwanted_sensors:
                    if unwanted in batch['sensors']:
                        del batch['sensors'][unwanted]
                        logging.info(f"Removed unwanted sensor type: {unwanted}")
        
        for sensor_type in requested_sensors:
            logger.info(f"DEBUG: Processing sensor_type: {sensor_type}")
            # Determine unit first (outside of if-else)
            unit = None
            if sensor_type == 'temperature':
                unit = '°C'
            elif sensor_type == 'minerals':
                unit = 'kg'
            elif sensor_type == 'DO':
                unit = 'mg/L'
            elif sensor_type == 'pH':
                unit = 'pH'
            elif sensor_type == 'shrimpSize':
                unit = 'cm'
            
            data_points = []
            values = []
            
            # Special handling for shrimpSize - get data from ShrimpSizeStorage
            if sensor_type == 'shrimpSize':
                logger.info(f"DEBUG: Processing shrimpSize for pond {pond_id}, timeframe {timeframe}")
                try:
                    shrimp_size_storage = ShrimpSizeStorage()
                    shrimp_batches = shrimp_size_storage.get_by_timeframe(pond_id, hours, timeframe)
                    logger.info(f"DEBUG: Found {len(shrimp_batches)} shrimp size batches for pond {pond_id}, timeframe {timeframe}")
                    
                    for batch in shrimp_batches:
                        try:
                            # Parse timestamp
                            timestamp_str = batch.get('timestamp', '')
                            if timestamp_str:
                                if timestamp_str.endswith('Z'):
                                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                                else:
                                    timestamp = datetime.fromisoformat(timestamp_str)
                                # Ensure timezone-naive for consistent processing
                                if timestamp.tzinfo is not None:
                                    timestamp = timestamp.replace(tzinfo=None)
                            else:
                                timestamp = datetime.now()
                            
                            # Get shrimp size value
                            shrimp_size = batch.get('shrimp_size', 0.0)
                            if isinstance(shrimp_size, (int, float)):
                                value = float(shrimp_size)
                            else:
                                value = 0.0
                            
                            # Determine status based on value
                            if value < 3.0:
                                status = 'red'
                            elif value < 4.0:
                                status = 'yellow'
                            else:
                                status = 'green'
                            
                            data_points.append({
                                'timestamp': timestamp.isoformat(),
                                'value': value,
                                'status': status
                            })
                            values.append(value)
                        except Exception as e:
                            logger.warning(f"Error processing shrimp size data: {e}")
                            continue
                except Exception as e:
                    logger.error(f"Error getting shrimp size data: {e}")
            else:
                # Regular sensor data processing
                for batch in batches:
                    if sensor_type in batch.get('sensors', {}):
                        sensor_data = batch['sensors'][sensor_type]
                        if sensor_data.get('type') == 'numeric':
                            try:
                                # Simple timestamp parsing
                                timestamp_str = batch.get('timestamp', '')
                                if timestamp_str:
                                    if timestamp_str.endswith('Z'):
                                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                                    else:
                                        timestamp = datetime.fromisoformat(timestamp_str)
                                    # Ensure timezone-naive for consistent processing
                                    if timestamp.tzinfo is not None:
                                        timestamp = timestamp.replace(tzinfo=None)
                                else:
                                    timestamp = datetime.now()
                                
                                value = float(sensor_data.get('value', 0.0))
                                status = sensor_data.get('status', 'green')
                                
                                data_points.append({
                                    'timestamp': timestamp.isoformat(),
                                    'value': value,
                                    'status': status
                                })
                                values.append(value)
                            except Exception as e:
                                logger.warning(f"Error processing sensor data: {e}")
                                continue
            
            if data_points:
                # For 1D timeframe, fill missing hours with 0.0 data
                if timeframe == "1D":
                    today = datetime.now().date()
                    existing_hours = set()
                    
                    # Get existing hours from real data
                    for point in data_points:
                        point_timestamp = datetime.fromisoformat(point['timestamp'].replace('Z', '+00:00'))
                        # Ensure timezone-naive for comparison
                        if point_timestamp.tzinfo is not None:
                            point_timestamp = point_timestamp.replace(tzinfo=None)
                        point_date = point_timestamp.date()
                        if point_date == today:
                            hour = point_timestamp.hour
                            existing_hours.add(hour)
                    
                    # Fill missing hours with 0.0 data
                    for hour in range(24):
                        if hour not in existing_hours:
                            timestamp = datetime.combine(today, datetime.min.time().replace(hour=hour))
                            data_points.append({
                                'timestamp': timestamp.isoformat(),
                                'value': 0.0,
                                'status': 'gray'
                            })
                    
                    # Sort data points by timestamp
                    def sort_key(x):
                        timestamp = datetime.fromisoformat(x['timestamp'].replace('Z', '+00:00'))
                        # Ensure timezone-naive for consistent sorting
                        if timestamp.tzinfo is not None:
                            timestamp = timestamp.replace(tzinfo=None)
                        return timestamp
                    data_points.sort(key=sort_key)
                
                # Debug logging
                logging.info(f"API: Created {len(data_points)} data points for {sensor_type}")
                
                # Calculate statistics (exclude 0.0 default values)
                real_values = [v for v in values if v > 0.0]
                min_val = round(min(real_values), 2) if real_values else 0.0
                max_val = round(max(real_values), 2) if real_values else 0.0
                avg_val = round(sum(real_values) / len(real_values), 2) if real_values else 0.0
                
                # Calculate trend (use only real values)
                trend = 'stable'
                if len(real_values) >= 2:
                    first_val = real_values[0]
                    last_val = real_values[-1]
                    if last_val > first_val * 1.05:
                        trend = 'increasing'
                    elif last_val < first_val * 0.95:
                        trend = 'decreasing'
                
                sensors_data[sensor_type] = {
                    'sensor_type': sensor_type,
                    'data_points': data_points,
                    'unit': unit,
                    'min_value': min_val,
                    'max_value': max_val,
                    'average_value': avg_val,
                    'trend': trend
                }
            else:
                # Create default data only for requested sensor types
                if sensor_type in requested_sensors:
                    default_points = []
                    
                    # Create default 0.0 data points for 1D timeframe to show baseline
                    if timeframe == "1D":
                        # Create hourly data points for today (00:00 to 23:00)
                        today = datetime.now().date()
                        for hour in range(24):
                            timestamp = datetime.combine(today, datetime.min.time().replace(hour=hour))
                            default_points.append({
                                'timestamp': timestamp.isoformat(),
                                'value': 0.0,
                                'status': 'gray'  # Gray status for default/waiting data
                            })
                    else:
                        # For 7D and 30D, create fewer default points
                        if timeframe == "7D":
                            # Create daily points for last 7 days
                            for day_offset in range(7):
                                date = datetime.now().date() - timedelta(days=day_offset)
                                timestamp = datetime.combine(date, datetime.min.time().replace(hour=12))
                                default_points.append({
                                    'timestamp': timestamp.isoformat(),
                                    'value': 0.0,
                                    'status': 'gray'
                                })
                        elif timeframe == "30D":
                            # Create every 3rd day for last 30 days
                            for day_offset in range(0, 30, 3):
                                date = datetime.now().date() - timedelta(days=day_offset)
                                timestamp = datetime.combine(date, datetime.min.time().replace(hour=12))
                                default_points.append({
                                    'timestamp': timestamp.isoformat(),
                                    'value': 0.0,
                                    'status': 'gray'
                                })
                
                sensors_data[sensor_type] = {
                    'sensor_type': sensor_type,
                    'data_points': default_points,
                    'unit': unit,
                    'min_value': 0.0,
                    'max_value': 0.0,
                    'average_value': 0.0,
                    'trend': 'stable'
                }
        
        # Final filter to ensure only requested sensor types in response
        filtered_sensors_data = {}
        for sensor_type, sensor_data in sensors_data.items():
            if sensor_type in requested_sensors:
                filtered_sensors_data[sensor_type] = sensor_data
        
        # Calculate actual time range based on filtered data
        actual_start_time = start_time if 'start_time' in locals() else (datetime.now() - timedelta(hours=hours))
        actual_end_time = end_time if 'end_time' in locals() else datetime.now()
        
        return {
            'success': True,
            'pond_id': pond_id,
            'sensors': filtered_sensors_data,
            'time_range': {
                'start_time': actual_start_time.isoformat(),
                'end_time': actual_end_time.isoformat()
            },
            'total_points': sum(len(sensor['data_points']) for sensor in filtered_sensors_data.values()),
            'timeframe': timeframe,
            'hours': hours
        }
        
    except Exception as e:
        logger.error(f"Error getting simple sensor graph data: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'pond_id': pond_id,
            'sensors': {},
            'time_range': {
                'start_time': (datetime.now() - timedelta(hours=24)).isoformat(),
                'end_time': datetime.now().isoformat()
            },
            'total_points': 0
        }

# ShrimpSize Graph endpoint
@router.get("/graph-shrimpsize/{pond_id}", response_model=dict)
async def get_shrimp_size_graph_data(
    pond_id: int,
    hours: int = Query(24, ge=1, le=720, description="Number of hours to fetch data for"),
    timeframe: str = Query("1D", description="Timeframe: 1D, 7D, or 30D")
):
    """
    Get shrimp size data formatted for graph visualization
    """
    try:
        # Get shrimp size data using ShrimpSizeStorage
        shrimp_size_storage = ShrimpSizeStorage()
        batches = shrimp_size_storage.get_by_timeframe(pond_id, hours, timeframe)
        
        # Debug logging
        logger.info(f"API: Found {len(batches)} shrimp size batches for pond {pond_id}")
        
        # Filter data by timeframe like other sensors
        if batches:
            # Sort by timestamp to ensure correct filtering
            def batch_sort_key(x):
                timestamp = datetime.fromisoformat(x['timestamp'].replace('Z', '+00:00'))
                # Ensure timezone-naive for consistent sorting
                if timestamp.tzinfo is not None:
                    timestamp = timestamp.replace(tzinfo=None)
                return timestamp
            batches.sort(key=batch_sort_key)
            
            # Filter by time range based on timeframe
            end_time = datetime.now().replace(tzinfo=None)  # Make timezone-naive
            
            # Adjust time range based on timeframe
            if timeframe == "1D":
                # For 1D, show only today (00:00 to 23:59:59)
                start_time = end_time.replace(hour=0, minute=0, second=0, microsecond=0)
                end_time = end_time.replace(hour=23, minute=59, second=59, microsecond=999999)
            elif timeframe == "7D":
                # For 7D, show last 7 days
                start_time = end_time - timedelta(days=7)
            elif timeframe == "30D":
                # For 30D, show last 30 days
                start_time = end_time - timedelta(days=30)
            else:
                # Default to hours-based filtering
                start_time = end_time - timedelta(hours=hours)
            
            filtered_batches = []
            for batch in batches:
                try:
                    batch_time = datetime.fromisoformat(batch['timestamp'].replace('Z', '+00:00'))
                    # Ensure timezone-naive for comparison
                    if batch_time.tzinfo is not None:
                        batch_time_naive = batch_time.replace(tzinfo=None)
                    else:
                        batch_time_naive = batch_time
                    
                    # For 1D timeframe, ensure we only get today's data
                    if timeframe == "1D":
                        batch_date = batch_time_naive.date()
                        today_date = end_time.date()
                        if batch_date == today_date:
                            filtered_batches.append(batch)
                    else:
                        if start_time <= batch_time_naive <= end_time:
                            filtered_batches.append(batch)
                except Exception as e:
                    logging.warning(f"Error parsing timestamp {batch.get('timestamp')}: {e}")
                    continue
            
            # Further filter for 7D and 30D to reduce data points
            if timeframe == "7D":
                # Keep only every 2nd hour for 7D, but ensure we include the latest data
                if len(filtered_batches) > 0:
                    # Always include the last batch (most recent data)
                    last_batch = filtered_batches[-1]
                    # Filter every 2nd batch, but keep the last one
                    filtered_batches = [batch for i, batch in enumerate(filtered_batches[:-1]) if i % 2 == 0] + [last_batch]
            elif timeframe == "30D":
                # Keep only every 4th hour for 30D, but ensure we include the latest data
                if len(filtered_batches) > 0:
                    # Always include the last batch (most recent data)
                    last_batch = filtered_batches[-1]
                    # Filter every 4th batch, but keep the last one
                    filtered_batches = [batch for i, batch in enumerate(filtered_batches[:-1]) if i % 4 == 0] + [last_batch]
            
            batches = filtered_batches
            logging.info(f"API: Filtered to {len(batches)} shrimp size batches for timeframe {timeframe}")
        
        # Process data for shrimp size graph
        data_points = []
        values = []
        
        for batch in batches:
            try:
                # Parse timestamp
                timestamp_str = batch.get('timestamp', '')
                if timestamp_str:
                    if timestamp_str.endswith('Z'):
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    else:
                        timestamp = datetime.fromisoformat(timestamp_str)
                    # Ensure timezone-naive for consistent processing
                    if timestamp.tzinfo is not None:
                        timestamp = timestamp.replace(tzinfo=None)
                else:
                    timestamp = datetime.now()
                
                # Get shrimp size value
                shrimp_size = batch.get('shrimp_size', 0.0)
                if isinstance(shrimp_size, (int, float)):
                    value = float(shrimp_size)
                else:
                    value = 0.0
                
                # Determine status based on size
                if value > 6:
                    status = 'green'
                elif value > 4:
                    status = 'yellow'
                else:
                    status = 'red'
                
                data_points.append({
                    'timestamp': timestamp.isoformat(),
                    'value': value,
                    'status': status
                })
                values.append(value)
                
            except Exception as e:
                logger.warning(f"Error processing shrimp size data: {e}")
                continue
        
        # If no data, return empty data instead of creating default data
        if not data_points:
            # Return empty data structure to indicate no real data available
            pass
        
        # Calculate statistics
        min_val = min(values) if values else 0.0
        max_val = max(values) if values else 0.0
        avg_val = sum(values) / len(values) if values else 0.0
        
        # Calculate trend
        trend = 'stable'
        if len(values) >= 2:
            first_val = values[0]
            last_val = values[-1]
            if last_val > first_val * 1.05:
                trend = 'increasing'
            elif last_val < first_val * 0.95:
                trend = 'decreasing'
        
        # Create response
        shrimp_size_data = {
            'sensor_type': 'Shrimp Size (CM)',
            'data_points': data_points,
            'unit': 'cm',
            'min_value': min_val,
            'max_value': max_val,
            'average_value': avg_val,
            'trend': trend
        }
        
        return {
            'success': True,
            'pond_id': pond_id,
            'sensor_data': shrimp_size_data,
            'time_range': {
                'start_time': (datetime.now() - timedelta(hours=hours)).isoformat(),
                'end_time': datetime.now().isoformat()
            },
            'total_points': len(data_points),
            'timeframe': timeframe,
            'hours': hours
        }
        
    except Exception as e:
        logger.error(f"Error getting shrimp size graph data: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'pond_id': pond_id,
            'sensor_data': {
                'sensor_type': 'Shrimp Size (CM)',
                'data_points': [],
                'unit': 'cm',
                'min_value': 0.0,
                'max_value': 0.0,
                'average_value': 0.0,
                'trend': 'stable'
            },
            'time_range': {
                'start_time': (datetime.now() - timedelta(hours=hours)).isoformat(),
                'end_time': datetime.now().isoformat()
            },
            'total_points': 0
        }


@router.post("/add-test-data")
async def add_test_data():
    """Add test data to graph_data.json for testing real-time updates"""
    try:
        # Read existing data
        with open("data/graph_data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Add new test data for September 29
        new_data = {
            "id": "graph_demo_1D2_001",
            "pond_id": 1,
            "timestamp": "2025-09-29T00:00:00+00:00",
            "sensors": {
                "DO": {
                    "value": 12.555555,
                    "type": "numeric",
                    "status": "green"
                },
                "pH": {
                    "value": 12.0,
                    "type": "numeric",
                    "status": "green"
                },
                "temperature": {
                    "value": 15.0,
                    "type": "numeric",
                    "status": "yellow"
                }
            }
        }
        
        # Add more test data for different hours
        for hour in range(1, 24):
            hour_data = {
                "id": f"graph_demo_1D2_{hour:03d}",
                "pond_id": 1,
                "timestamp": f"2025-09-29T{hour:02d}:00:00+00:00",
                "sensors": {
                    "DO": {
                        "value": 12.555555 + (hour * 0.1),
                        "type": "numeric",
                        "status": "green"
                    },
                    "pH": {
                        "value": 12.0 + (hour * 0.05),
                        "type": "numeric",
                        "status": "green"
                    },
                    "temperature": {
                        "value": 15.0 + (hour * 0.2),
                        "type": "numeric",
                        "status": "yellow" if hour < 12 else "green"
                    }
                }
            }
            data.append(hour_data)
        
        # Write back to file
        with open("data/graph_data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return {
            "message": "Test data added successfully",
            "added_records": 24,
            "date": "2025-09-29"
        }
        
    except Exception as e:
        logging.error(f"Error adding test data: {e}")
        raise HTTPException(status_code=500, detail=f"Error adding test data: {str(e)}")


@router.post("/add-future-test-data")
async def add_future_test_data():
    """Add test data for tomorrow (September 30) for testing future data"""
    try:
        # Read existing data
        with open("data/graph_data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Add test data for September 30 (tomorrow)
        for hour in range(0, 24):
            hour_data = {
                "id": f"graph_demo_future_{hour:03d}",
                "pond_id": 1,
                "timestamp": f"2025-09-30T{hour:02d}:00:00+00:00",
                "sensors": {
                    "DO": {
                        "value": 8.0 + (hour * 0.3),
                        "type": "numeric",
                        "status": "green" if hour < 8 else "yellow" if hour < 16 else "red"
                    },
                    "pH": {
                        "value": 6.5 + (hour * 0.1),
                        "type": "numeric",
                        "status": "green"
                    },
                    "temperature": {
                        "value": 20.0 + (hour * 0.5),
                        "type": "numeric",
                        "status": "green" if hour < 12 else "yellow"
                    }
                }
            }
            data.append(hour_data)
        
        # Write back to file
        with open("data/graph_data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return {
            "message": "Future test data added successfully",
            "added_records": 24,
            "date": "2025-09-30"
        }
        
    except Exception as e:
        logging.error(f"Error adding future test data: {e}")
        raise HTTPException(status_code=500, detail=f"Error adding future test data: {str(e)}")


# Routine Settings Endpoints
@router.get("/routine-settings/{pond_id}", response_model=dict)
async def get_routine_settings(pond_id: int):
    """Get routine settings for a specific pond"""
    try:
        routine_storage = RoutineStorage()
        routines = routine_storage.get_pond_routines(pond_id)
        
        return {
            "success": True,
            "pond_id": pond_id,
            "routines": routines
        }
    except Exception as e:
        logger.error(f"Error getting routine settings: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting routine settings: {str(e)}")

@router.post("/routine-settings/{pond_id}", response_model=dict)
async def save_routine_settings(pond_id: int, routines: dict):
    """Save routine settings for a specific pond"""
    try:
        routine_storage = RoutineStorage()
        routine_storage.save_pond_routines(pond_id, routines)
        
        return {
            "success": True,
            "pond_id": pond_id,
            "message": "Routine settings saved successfully"
        }
    except Exception as e:
        logger.error(f"Error saving routine settings: {e}")
        raise HTTPException(status_code=500, detail=f"Error saving routine settings: {str(e)}")

@router.post("/routine-settings/{pond_id}/schedule", response_model=dict)
async def add_routine_schedule(pond_id: int, schedule: dict):
    """Add a new routine schedule"""
    try:
        routine_storage = RoutineStorage()
        schedule_id = routine_storage.add_schedule(pond_id, schedule)
        
        return {
            "success": True,
            "pond_id": pond_id,
            "schedule_id": schedule_id,
            "message": "Schedule added successfully"
        }
    except Exception as e:
        logger.error(f"Error adding routine schedule: {e}")
        raise HTTPException(status_code=500, detail=f"Error adding routine schedule: {str(e)}")

@router.delete("/routine-settings/{pond_id}/schedule/{schedule_id}", response_model=dict)
async def remove_routine_schedule(pond_id: int, schedule_id: str):
    """Remove a routine schedule"""
    try:
        routine_storage = RoutineStorage()
        success = routine_storage.remove_schedule(pond_id, schedule_id)
        
        if success:
            return {
                "success": True,
                "pond_id": pond_id,
                "schedule_id": schedule_id,
                "message": "Schedule removed successfully"
            }
        else:
            raise HTTPException(status_code=404, detail="Schedule not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing routine schedule: {e}")
        raise HTTPException(status_code=500, detail=f"Error removing routine schedule: {str(e)}")

class ToggleRequest(BaseModel):
    enabled: bool

@router.post("/routine-settings/{pond_id}/toggle", response_model=dict)
async def toggle_routine_enabled(pond_id: int, request_data: ToggleRequest):
    """Toggle routine enabled status"""
    try:
        enabled = request_data.enabled
        routine_storage = RoutineStorage()
        routine_storage.toggle_routine_enabled(pond_id, enabled)
        
        return {
            "success": True,
            "pond_id": pond_id,
            "enabled": enabled,
            "message": f"Routine {'enabled' if enabled else 'disabled'} successfully"
        }
    except Exception as e:
        logger.error(f"Error toggling routine enabled: {e}")
        raise HTTPException(status_code=500, detail=f"Error toggling routine enabled: {str(e)}")

@router.get("/routine-settings/all/enabled", response_model=dict)
async def get_all_enabled_schedules():
    """Get all enabled schedules from all ponds"""
    try:
        routine_storage = RoutineStorage()
        schedules = routine_storage.get_all_enabled_schedules()
        
        return {
            "success": True,
            "schedules": schedules,
            "count": len(schedules)
        }
    except Exception as e:
        logger.error(f"Error getting all enabled schedules: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting all enabled schedules: {str(e)}")
