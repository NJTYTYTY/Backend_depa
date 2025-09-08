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
MEDIA_ASSETS_FILE = STORAGE_DIR / "media_assets.json"
INSIGHTS_FILE = STORAGE_DIR / "insights.json"
CONTROL_LOGS_FILE = STORAGE_DIR / "control_logs.json"

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
    for file_path in [USERS_FILE, PONDS_FILE, SENSOR_READINGS_FILE, MEDIA_ASSETS_FILE, INSIGHTS_FILE, CONTROL_LOGS_FILE]:
        if not file_path.exists():
            JSONStorage._write_json(file_path, [])
            logging.info(f"Created {file_path}")
