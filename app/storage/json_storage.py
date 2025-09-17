"""
JSON-based data storage for Backend_PWA
Replaces SQLite database with JSON file storage
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

# Storage directory - use absolute path for Railway deployment
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "data"))
try:
    STORAGE_DIR.mkdir(exist_ok=True)
except Exception as e:
    logging.warning(f"Could not create storage directory {STORAGE_DIR}: {e}")
    # Fallback to current directory
    STORAGE_DIR = Path(".")

# JSON file paths
USERS_FILE = STORAGE_DIR / "users.json"
PONDS_FILE = STORAGE_DIR / "ponds.json"
SENSOR_READINGS_FILE = STORAGE_DIR / "sensor_readings.json"
SENSOR_BATCHES_FILE = STORAGE_DIR / "sensor_batches.json"
MEDIA_ASSETS_FILE = STORAGE_DIR / "media_assets.json"

class JSONStorage:
    """JSON-based data storage class"""
    
    @staticmethod
    def _read_json(file_path: Path) -> List[Dict[str, Any]]:
        """Read data from JSON file"""
        if not file_path.exists():
            return []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logging.error(f"Error reading {file_path}: {e}")
            return []
    
    @staticmethod
    def _write_json(file_path: Path, data: List[Dict[str, Any]]) -> bool:
        """Write data to JSON file"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logging.error(f"Error writing {file_path}: {e}")
            return False
    
    @staticmethod
    def _generate_id(items: List[Dict[str, Any]]) -> int:
        """Generate next ID for new item"""
        if not items:
            return 1
        return max(item.get('id', 0) for item in items) + 1

class UserStorage(JSONStorage):
    """User data storage operations"""
    
    @staticmethod
    def get_all() -> List[Dict[str, Any]]:
        """Get all users"""
        return JSONStorage._read_json(USERS_FILE)
    
    @staticmethod
    def get_by_id(user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        users = UserStorage.get_all()
        return next((user for user in users if user.get('id') == user_id), None)
    
    @staticmethod
    def get_by_phone(phone_number: str) -> Optional[Dict[str, Any]]:
        """Get user by phone number"""
        users = UserStorage.get_all()
        return next((user for user in users if user.get('phone_number') == phone_number), None)
    
    @staticmethod
    def get_by_email(email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        users = UserStorage.get_all()
        return next((user for user in users if user.get('email') == email), None)
    
    @staticmethod
    def create(user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new user"""
        users = UserStorage.get_all()
        user_data['id'] = JSONStorage._generate_id(users)
        user_data['created_at'] = datetime.utcnow().isoformat()
        user_data['updated_at'] = datetime.utcnow().isoformat()
        
        users.append(user_data)
        JSONStorage._write_json(USERS_FILE, users)
        return user_data
    
    @staticmethod
    def update(user_id: int, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update user"""
        users = UserStorage.get_all()
        for i, user in enumerate(users):
            if user.get('id') == user_id:
                update_data['updated_at'] = datetime.utcnow().isoformat()
                users[i] = {**user, **update_data}
                JSONStorage._write_json(USERS_FILE, users)
                return users[i]
        return None
    
    @staticmethod
    def delete(user_id: int) -> bool:
        """Delete user"""
        users = UserStorage.get_all()
        users = [user for user in users if user.get('id') != user_id]
        return JSONStorage._write_json(USERS_FILE, users)
    
    @staticmethod
    def count() -> int:
        """Get user count"""
        return len(UserStorage.get_all())

class PondStorage(JSONStorage):
    """Pond data storage operations"""
    
    @staticmethod
    def get_all() -> List[Dict[str, Any]]:
        """Get all ponds"""
        return JSONStorage._read_json(PONDS_FILE)
    
    @staticmethod
    def get_by_id(pond_id: int) -> Optional[Dict[str, Any]]:
        """Get pond by ID"""
        ponds = PondStorage.get_all()
        return next((pond for pond in ponds if pond.get('id') == pond_id), None)
    
    @staticmethod
    def get_by_owner(owner_id: int) -> List[Dict[str, Any]]:
        """Get ponds by owner ID"""
        ponds = PondStorage.get_all()
        return [pond for pond in ponds if pond.get('owner_id') == owner_id]
    
    @staticmethod
    def create(pond_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new pond"""
        ponds = PondStorage.get_all()
        pond_data['id'] = JSONStorage._generate_id(ponds)
        pond_data['created_at'] = datetime.utcnow().isoformat()
        pond_data['updated_at'] = datetime.utcnow().isoformat()
        
        ponds.append(pond_data)
        JSONStorage._write_json(PONDS_FILE, ponds)
        return pond_data
    
    @staticmethod
    def update(pond_id: int, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update pond"""
        ponds = PondStorage.get_all()
        for i, pond in enumerate(ponds):
            if pond.get('id') == pond_id:
                update_data['updated_at'] = datetime.utcnow().isoformat()
                ponds[i] = {**pond, **update_data}
                JSONStorage._write_json(PONDS_FILE, ponds)
                return ponds[i]
        return None
    
    @staticmethod
    def delete(pond_id: int) -> bool:
        """Delete pond"""
        ponds = PondStorage.get_all()
        ponds = [pond for pond in ponds if pond.get('id') != pond_id]
        return JSONStorage._write_json(PONDS_FILE, ponds)
    
    @staticmethod
    def count() -> int:
        """Get pond count"""
        return len(PondStorage.get_all())

class SensorReadingStorage(JSONStorage):
    """Sensor reading data storage operations"""
    
    @staticmethod
    def get_all() -> List[Dict[str, Any]]:
        """Get all sensor readings"""
        return JSONStorage._read_json(SENSOR_READINGS_FILE)
    
    @staticmethod
    def get_by_pond(pond_id: int) -> List[Dict[str, Any]]:
        """Get sensor readings by pond ID"""
        readings = SensorReadingStorage.get_all()
        return [reading for reading in readings if reading.get('pond_id') == pond_id]
    
    @staticmethod
    def create(reading_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new sensor reading"""
        readings = SensorReadingStorage.get_all()
        reading_data['id'] = JSONStorage._generate_id(readings)
        reading_data['created_at'] = datetime.utcnow().isoformat()
        
        readings.append(reading_data)
        JSONStorage._write_json(SENSOR_READINGS_FILE, readings)
        return reading_data
    
    @staticmethod
    def get_latest_readings(pond_id: int) -> List[Dict[str, Any]]:
        """Get latest sensor readings for a pond by sensor type"""
        readings = SensorReadingStorage.get_by_pond(pond_id)
        
        # Group by sensor_type and get latest for each
        latest_by_type = {}
        for reading in readings:
            sensor_type = reading.get('sensor_type')
            if sensor_type:
                if sensor_type not in latest_by_type:
                    latest_by_type[sensor_type] = reading
                else:
                    # Compare timestamps to get the latest
                    current_time = reading.get('timestamp', '')
                    existing_time = latest_by_type[sensor_type].get('timestamp', '')
                    if current_time > existing_time:
                        latest_by_type[sensor_type] = reading
        
        return list(latest_by_type.values())

class SensorBatchStorage(JSONStorage):
    """Sensor batch data storage operations - OPTIMIZED for bulk sensor data"""
    
    @staticmethod
    def get_all() -> List[Dict[str, Any]]:
        """Get all sensor batches"""
        return JSONStorage._read_json(SENSOR_BATCHES_FILE)
    
    @staticmethod
    def get_by_pond(pond_id: int) -> List[Dict[str, Any]]:
        """Get sensor batches by pond ID"""
        batches = SensorBatchStorage.get_all()
        return [batch for batch in batches if batch.get('pond_id') == pond_id]
    
    @staticmethod
    def get_by_id(batch_id: str) -> Optional[Dict[str, Any]]:
        """Get sensor batch by ID"""
        batches = SensorBatchStorage.get_all()
        return next((batch for batch in batches if batch.get('id') == batch_id), None)
    
    @staticmethod
    def create(batch_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new sensor batch"""
        batches = SensorBatchStorage.get_all()
        batch_data['created_at'] = datetime.utcnow().isoformat()
        
        batches.append(batch_data)
        JSONStorage._write_json(SENSOR_BATCHES_FILE, batches)
        return batch_data
    
    @staticmethod
    def get_latest_batch(pond_id: int) -> Optional[Dict[str, Any]]:
        """Get latest sensor batch for a pond (always get the last array element)"""
        batches = SensorBatchStorage.get_by_pond(pond_id)
        if not batches:
            return None
        
        # Always get the last element in the array (most recent)
        latest = batches[-1]
        return latest
    
    @staticmethod
    def get_latest_batch(pond_id: int) -> Optional[Dict[str, Any]]:
        """Get latest sensor batch for a pond WITHOUT removing it from storage"""
        all_batches = SensorBatchStorage.get_all()
        pond_batches = [batch for batch in all_batches if batch.get('pond_id') == pond_id]
        
        if not pond_batches:
            return None
        
        # Get the last batch for this pond
        latest_batch = pond_batches[-1]
        
        # DON'T remove the batch - just return it
        # This allows multiple reads of the same data
        
        return latest_batch
    
    @staticmethod
    def get_latest_sensors(pond_id: int) -> Dict[str, Any]:
        """Get latest sensor values for a pond (optimized for frontend)"""
        latest_batch = SensorBatchStorage.get_latest_batch(pond_id)
        if not latest_batch:
            return {}
        
        # Extract sensors data in frontend-friendly format
        sensors = latest_batch.get('sensors', {})
        result = {}
        
        for sensor_type, data in sensors.items():
            result[sensor_type] = {
                'value': data.get('value'),
                'status': data.get('status'),
                'type': data.get('type'),
                'timestamp': latest_batch.get('timestamp')
            }
        
        return result
    
    @staticmethod
    def get_batch_history(pond_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get batch history for a pond"""
        batches = SensorBatchStorage.get_by_pond(pond_id)
        
        # Return the last N batches (most recent first)
        return batches[-limit:] if len(batches) >= limit else batches
    
    @staticmethod
    def clear_all() -> bool:
        """Clear all sensor batch data"""
        return JSONStorage._write_json(SENSOR_BATCHES_FILE, [])
    
    @staticmethod
    def clear_by_pond(pond_id: int) -> bool:
        """Clear sensor batch data for a specific pond"""
        all_batches = SensorBatchStorage.get_all()
        filtered_batches = [batch for batch in all_batches if batch.get('pond_id') != pond_id]
        return JSONStorage._write_json(SENSOR_BATCHES_FILE, filtered_batches)
    
    @staticmethod
    def delete_latest_batch(pond_id: int) -> Optional[Dict[str, Any]]:
        """Delete the latest sensor batch for a specific pond and return the deleted batch"""
        all_batches = SensorBatchStorage.get_all()
        pond_batches = [batch for batch in all_batches if batch.get('pond_id') == pond_id]
        
        if not pond_batches:
            return None
        
        # Get the latest batch (last in the list)
        latest_batch = pond_batches[-1]
        
        # Remove the latest batch from all batches
        remaining_batches = [batch for batch in all_batches if batch.get('id') != latest_batch.get('id')]
        
        # Write back to file
        success = JSONStorage._write_json(SENSOR_BATCHES_FILE, remaining_batches)
        
        if success:
            return latest_batch
        else:
            return None
    
    @staticmethod
    def get_batches_by_pond_and_time_range(pond_id: int, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get sensor batches for a pond within a specific time range"""
        all_batches = SensorBatchStorage.get_all()
        pond_batches = [batch for batch in all_batches if batch.get('pond_id') == pond_id]
        
        filtered_batches = []
        for batch in pond_batches:
            try:
                # Parse timestamp from batch
                batch_timestamp_str = batch.get('timestamp', '')
                if batch_timestamp_str:
                    # Handle different timestamp formats
                    if 'T' in batch_timestamp_str:
                        if batch_timestamp_str.endswith('Z'):
                            batch_timestamp = datetime.fromisoformat(batch_timestamp_str.replace('Z', '+00:00'))
                        else:
                            batch_timestamp = datetime.fromisoformat(batch_timestamp_str)
                    else:
                        # Fallback for other formats
                        batch_timestamp = datetime.fromisoformat(batch_timestamp_str)
                    
                    # Check if timestamp is within range
                    if start_time <= batch_timestamp <= end_time:
                        filtered_batches.append(batch)
            except (ValueError, TypeError) as e:
                logging.warning(f"Error parsing timestamp for batch {batch.get('id', 'unknown')}: {e}")
                continue
        
        # Sort by timestamp (oldest first)
        filtered_batches.sort(key=lambda x: x.get('timestamp', ''))
        return filtered_batches

class MediaAssetStorage(JSONStorage):
    """Media asset data storage operations"""
    
    @staticmethod
    def get_all() -> List[Dict[str, Any]]:
        """Get all media assets"""
        return JSONStorage._read_json(MEDIA_ASSETS_FILE)
    
    @staticmethod
    def get_by_pond(pond_id: int) -> List[Dict[str, Any]]:
        """Get media assets by pond ID"""
        assets = MediaAssetStorage.get_all()
        return [asset for asset in assets if asset.get('pond_id') == pond_id]
    
    @staticmethod
    def create(asset_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new media asset"""
        assets = MediaAssetStorage.get_all()
        asset_data['id'] = JSONStorage._generate_id(assets)
        asset_data['upload_date'] = datetime.utcnow().isoformat()
        asset_data['last_modified'] = datetime.utcnow().isoformat()
        asset_data['download_count'] = 0
        asset_data['view_count'] = 0
        
        assets.append(asset_data)
        JSONStorage._write_json(MEDIA_ASSETS_FILE, assets)
        return asset_data

# Initialize storage with default admin user if no users exist
def initialize_storage():
    """Initialize JSON storage with default data"""
    users = UserStorage.get_all()
    if not users:
        # Create default admin user
        admin_user = {
            "phone_number": "0812345678",
            "email": "admin@backend-pwa.com",
            "full_name": "System Administrator",
            "password": "admin123",
            "role": "admin",
            "is_admin": True,
            "is_active": True
        }
        UserStorage.create(admin_user)
        logging.info("Created default admin user")
    
    # Ensure all storage directories exist
    for file_path in [USERS_FILE, PONDS_FILE, SENSOR_READINGS_FILE, SENSOR_BATCHES_FILE, MEDIA_ASSETS_FILE]:
        if not file_path.exists():
            JSONStorage._write_json(file_path, [])
            logging.info(f"Created {file_path}")
