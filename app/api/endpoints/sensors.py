"""
Sensor data management endpoints for Backend_PWA
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from datetime import datetime, timedelta
import logging

from ...storage import SensorReadingStorage, SensorBatchStorage, PondStorage
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
        },
        'DO': {
            'yellow': [(3, 5)],
            'red': [(0, 2.9)]
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
      "DO": 9.8,
      "PH": 7.5,
      "Temp": 25,
      "Size": 9.9,
      "Mineral": 50,
      "SizePic": "https://exampleUrl.com",
      "PicFood": "https://exampleUrl.com",
      "PicColorWater": "https://exampleUrl.com"
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
            'Size': 'shrimpSize',
            'Mineral': 'minerals',
            'ColorWater': 'waterColor',  # ColorWater with status (green/yellow/red)
            'SizePic': 'sizePicture',
            'PicFood': 'foodPicture', 
            'PicColorWater': 'waterColorPicture'  # PicColorWater with URL
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
                    if key in ['SizePic', 'PicFood', 'PicColorWater']:
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
                        # These are numeric values
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
            "source": "batch_api"
        }
        
        # Store in batch storage
        batch_storage = SensorBatchStorage()
        stored_batch = batch_storage.create(batch_data)
        
        logger.info(f"Stored batch {batch_id} with {len(sensors_data)} sensors for pond {pond_id}")
        
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

# New endpoint for receiving bulk sensor data in JSON format (LEGACY)
@router.post("/bulk-sensor-data", response_model=dict, status_code=status.HTTP_201_CREATED)
async def receive_bulk_sensor_data(
    request_data: dict,
):
    """
    Receive bulk sensor data in JSON format (LEGACY - use /batch-sensor-data instead):
    {
      "pondId": "1",
      "timestamp": "2024-01-01T12:00:00.000Z",
      "DO": 9.8,
      "PH": 7.5,
      "Temp": 25,
      "Size": 9.9,
      "Mineral": 50,
      "SizePic": "https://exampleUrl.com",
      "PicFood": "https://exampleUrl.com",
      "PicColorWater": "https://exampleUrl.com"
    }
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
            except ValueError:
                timestamp = datetime.utcnow()
        else:
            timestamp = datetime.utcnow()
        
        # Parse the sensor data from JSON object
        # Map keys to sensor types
        sensor_mapping = {
            'DO': 'DO',
            'PH': 'pH', 
            'Temp': 'temperature',
            'Size': 'shrimpSize',
            'Mineral': 'minerals',
            'SizePic': 'sizePicture',
            'PicFood': 'foodPicture', 
            'PicColorWater': 'waterColorPicture'
        }
        
        parsed_data = {}
        
        # Process each sensor data field
        for key, value in request_data.items():
            if key in ['pondId', 'timestamp']:
                continue  # Skip metadata fields
                
            if key in sensor_mapping:
                sensor_type = sensor_mapping[key]
                
                # Handle different value types
                if key in ['SizePic', 'PicFood', 'PicColorWater']:
                    # These are URLs
                    parsed_data[sensor_type] = {
                        'value': str(value),
                        'type': 'url'
                    }
                else:
                    # These are numeric values
                    try:
                        numeric_value = float(value)
                        parsed_data[sensor_type] = {
                            'value': numeric_value,
                            'type': 'numeric'
                        }
                    except (ValueError, TypeError):
                        # If not numeric, store as string
                        parsed_data[sensor_type] = {
                            'value': str(value),
                            'type': 'string'
                        }
        
        # Store sensor readings
        storage = SensorReadingStorage()
        stored_readings = []
        
        for sensor_type, data in parsed_data.items():
            if data['type'] == 'numeric':
                # Calculate status for numeric sensors
                calculated_status = calculate_sensor_status(sensor_type, data['value'])
                
                # Create sensor reading data
                reading_data = {
                    "id": f"sensor_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}_{sensor_type}",
                    "pond_id": pond_id,
                    "sensor_type": sensor_type,
                    "value": data['value'],
                    "status": calculated_status,
                    "timestamp": timestamp.isoformat(),
                    "meta_data": {
                        "type": data['type'],
                        "source": "bulk_template"
                    }
                }
                
                # Store the reading
                stored_reading = storage.create(reading_data)
                stored_readings.append(stored_reading)
                
                logger.info(f"Stored {sensor_type}={data['value']} for pond {pond_id} (status: {calculated_status})")
            else:
                # For non-numeric data, store as metadata
                reading_data = {
                    "id": f"sensor_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}_{sensor_type}",
                    "pond_id": pond_id,
                    "sensor_type": sensor_type,
                    "value": data['value'],
                    "status": "info",
                    "timestamp": timestamp.isoformat(),
                    "meta_data": {
                        "type": data['type'],
                        "source": "bulk_template",
                        "data": data['value']
                    }
                }
                
                # Store the reading
                stored_reading = storage.create(reading_data)
                stored_readings.append(stored_reading)
                
                logger.info(f"Stored {sensor_type}={data['value']} for pond {pond_id} (type: {data['type']})")
        
        # Return success response
        return {
            "success": True,
            "message": f"Bulk sensor data received successfully ({len(stored_readings)} readings)",
            "data": {
                "pondId": pond_id,
                "timestamp": timestamp.isoformat(),
                "readings": stored_readings,
                "parsed_data": parsed_data
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing bulk sensor data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process bulk sensor data: {str(e)}"
        )

# New endpoint for receiving sensor data from test_request_get
# Single sensor endpoint removed - use batch-sensor-data instead

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


        
