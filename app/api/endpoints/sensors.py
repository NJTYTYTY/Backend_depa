"""
Sensor data management endpoints for Backend_PWA
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from datetime import datetime, timedelta
import logging

from ...storage import SensorReadingStorage, SensorBatchStorage, YorrKungStorage, PondStorage
from ...storage.graph_storage import GraphDataStorage
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
      "Mineral_3": 4800,
      "Mineral_4": 4800,
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
                        # These are numeric values (including Mineral_1-4)
                        try:
                            numeric_value = float(value)
                            # For Mineral_1-4 fields, use 'minerals' sensor type for status calculation
                            status_sensor_type = 'minerals' if sensor_type.startswith('minerals_') else sensor_type
                            calculated_status = calculate_sensor_status(status_sensor_type, numeric_value)
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
        
        logger.info(f"Stored batch {batch_id} with {len(sensors_data)} sensors for pond {pond_id}")
        
        # Send push notifications for sensor alerts
        try:
            from ...core.notification_triggers import notification_triggers
            from ...storage.pond_storage import PondStorage
            
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

# New endpoint for getting YorrKung batch history
@router.get("/yorrkung-batches/{pond_id}", response_model=dict)
async def get_yorrkung_batch_history(
    pond_id: int,
    limit: int = Query(10, ge=1, le=100, description="Number of YorrKung batches to return")
):
    """
    Get YorrKung batch history for a specific pond
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
        
        # Get YorrKung batch history
        yorrkung_storage = YorrKungStorage()
        batches = yorrkung_storage.get_batch_history(pond_id, limit)
        
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
        logger.error(f"Error getting YorrKung batch history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get YorrKung batch history: {str(e)}"
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
async def get_sensor_graph_data_simple(pond_id: int, hours: int = 24):
    """
    Get sensor data formatted for graph visualization (simple version)
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
            for sensor_type in ['DO', 'pH', 'temperature', 'shrimpSize', 'minerals']:
                if sensor_type in batches[0].get('sensors', {}):
                    sensor_data = batches[0]['sensors'][sensor_type]
                    logging.info(f"API: {sensor_type} data: {sensor_data}")
                else:
                    logging.info(f"API: {sensor_type} not found in sensors")
        
        # Take only the last N batches based on hours parameter
        batches = batches[-hours:] if len(batches) > hours else batches
        
        # Process data for each sensor type
        sensors_data = {}
        numeric_sensors = ['DO', 'pH', 'temperature', 'shrimpSize', 'minerals']
        
        for sensor_type in numeric_sensors:
            # Determine unit first (outside of if-else)
            unit = None
            if sensor_type == 'temperature':
                unit = '°C'
            elif sensor_type == 'shrimpSize':
                unit = 'cm'
            elif sensor_type == 'minerals':
                unit = 'kg'
            elif sensor_type == 'DO':
                unit = 'mg/L'
            elif sensor_type == 'pH':
                unit = 'pH'
            
            data_points = []
            values = []
            
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
                # Create default data
                default_points = []
                for i in range(24):
                    timestamp = datetime.now() - timedelta(hours=i)
                    default_points.append({
                        'timestamp': timestamp.isoformat(),
                        'value': 0.0,
                        'status': 'green'
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
        
        return {
            'success': True,
            'pond_id': pond_id,
            'sensors': sensors_data,
            'time_range': {
                'start_time': (datetime.now() - timedelta(hours=24)).isoformat(),
                'end_time': datetime.now().isoformat()
            },
            'total_points': sum(len(sensor['data_points']) for sensor in sensors_data.values())
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




        
