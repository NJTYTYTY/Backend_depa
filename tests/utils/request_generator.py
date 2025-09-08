"""
Test Request Generator Utility

This module provides utilities for generating test JSON requests to validate
API endpoints and sensor data processing.
"""

import json
import random
import string
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

def generate_sensor_data(pond_id: int, count: int = 10, sensor_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Generate realistic sensor data for testing
    
    Args:
        pond_id: ID of the pond
        count: Number of sensor readings to generate
        sensor_types: List of sensor types to use (default: all available types)
    
    Returns:
        List of sensor data dictionaries
    """
    if sensor_types is None:
        sensor_types = ['temperature', 'oxygen', 'ph', 'salinity', 'ammonia', 'turbidity', 'nitrite', 'nitrate']
    
    data = []
    
    for _ in range(count):
        sensor_type = random.choice(sensor_types)
        
        # Generate realistic values based on sensor type
        value_ranges = {
            'temperature': (20, 35),      # Celsius
            'oxygen': (2, 8),            # mg/L
            'ph': (6, 9),                # pH scale
            'salinity': (10, 20),        # ppt
            'ammonia': (0, 2),           # mg/L
            'turbidity': (0, 50),        # NTU
            'nitrite': (0, 1),           # mg/L
            'nitrate': (0, 5)            # mg/L
        }
        
        min_val, max_val = value_ranges.get(sensor_type, (0, 100))
        value = random.uniform(min_val, max_val)
        
        # Add some realistic variation (occasional anomalies)
        if random.random() < 0.1:  # 10% chance of anomaly
            if sensor_type == 'temperature':
                value = random.choice([random.uniform(35, 40), random.uniform(15, 20)])
            elif sensor_type == 'oxygen':
                value = random.uniform(0, 2)  # Low oxygen
            elif sensor_type == 'ph':
                value = random.choice([random.uniform(9, 11), random.uniform(4, 6)])
        
        # Generate timestamp within the last hour
        timestamp = datetime.now() - timedelta(minutes=random.randint(0, 60))
        
        data.append({
            "pond_id": pond_id,
            "sensor_type": sensor_type,
            "value": round(value, 2),
            "timestamp": timestamp.isoformat(),
            "location": random.choice(["surface", "middle", "bottom"]),
            "notes": f"Test data for {sensor_type} sensor"
        })
    
    return data

def generate_user_data(count: int = 5) -> List[Dict[str, Any]]:
    """
    Generate test user data
    
    Args:
        count: Number of users to generate
    
    Returns:
        List of user data dictionaries
    """
    users = []
    roles = ["admin", "owner", "operator", "viewer"]
    
    for i in range(count):
        username = f"testuser{i+1}"
        email = f"{username}@test.com"
        role = random.choice(roles)
        
        users.append({
            "username": username,
            "email": email,
            "password": "TestPassword123!",
            "full_name": f"Test User {i+1}",
            "role": role,
            "phone": f"+66{random.randint(800000000, 899999999)}",
            "is_active": True
        })
    
    return users

def generate_pond_data(count: int = 3) -> List[Dict[str, Any]]:
    """
    Generate test pond data
    
    Args:
        count: Number of ponds to generate
    
    Returns:
        List of pond data dictionaries
    """
    ponds = []
    locations = ["Bangkok", "Chiang Mai", "Phuket", "Pattaya", "Hua Hin"]
    pond_types = ["shrimp", "fish", "mixed", "ornamental"]
    
    for i in range(count):
        location = random.choice(locations)
        pond_type = random.choice(pond_types)
        
        ponds.append({
            "name": f"Test Pond {i+1}",
            "location": location,
            "size": round(random.uniform(100, 1000), 2),
            "depth": round(random.uniform(1, 3), 2),
            "pond_type": pond_type,
            "description": f"Test pond for {pond_type} farming in {location}",
            "is_active": True
        })
    
    return ponds

def generate_media_asset_data(pond_id: int, count: int = 5) -> List[Dict[str, Any]]:
    """
    Generate test media asset data
    
    Args:
        pond_id: ID of the pond
        count: Number of media assets to generate
    
    Returns:
        List of media asset data dictionaries
    """
    assets = []
    file_types = ["image", "video", "document", "audio"]
    categories = ["monitoring", "maintenance", "harvest", "equipment", "general"]
    
    for i in range(count):
        file_type = random.choice(file_types)
        category = random.choice(categories)
        
        # Generate appropriate file extension and size based on type
        if file_type == "image":
            extension = random.choice(["jpg", "png", "gif", "webp"])
            file_size = random.randint(100000, 5000000)  # 100KB - 5MB
        elif file_type == "video":
            extension = random.choice(["mp4", "avi", "mov", "webm"])
            file_size = random.randint(10000000, 100000000)  # 10MB - 100MB
        elif file_type == "document":
            extension = random.choice(["pdf", "doc", "txt"])
            file_size = random.randint(10000, 1000000)  # 10KB - 1MB
        else:  # audio
            extension = random.choice(["mp3", "wav", "ogg"])
            file_size = random.randint(1000000, 10000000)  # 1MB - 10MB
        
        assets.append({
            "title": f"Test {file_type.title()} {i+1}",
            "description": f"Test {file_type} asset for pond {pond_id}",
            "file_type": file_type,
            "file_extension": extension,
            "file_size": file_size,
            "mime_type": f"{file_type}/{extension}",
            "tags": [f"test", file_type, category],
            "is_public": random.choice([True, False]),
            "category": category,
            "pond_id": pond_id,
            "file_path": f"uploads/{pond_id}/test_{file_type}_{i+1}.{extension}",
            "original_filename": f"test_{file_type}_{i+1}.{extension}",
            "uploaded_by": 1  # Assuming user ID 1 exists
        })
    
    return assets

def generate_bulk_operations(count: int = 10) -> List[Dict[str, Any]]:
    """
    Generate test bulk operations data
    
    Args:
        count: Number of bulk operations to generate
    
    Returns:
        List of bulk operation data dictionaries
    """
    operations = []
    operation_types = ["delete", "make_public", "make_private", "update_category", "add_tags", "remove_tags"]
    
    for i in range(count):
        operation_type = random.choice(operation_types)
        
        operation_data = {
            "asset_ids": list(range(1, random.randint(2, 6))),  # 1-5 asset IDs
            "operation": operation_type
        }
        
        # Add operation-specific data
        if operation_type == "update_category":
            operation_data["category"] = random.choice(["monitoring", "maintenance", "harvest", "equipment"])
        elif operation_type in ["add_tags", "remove_tags"]:
            operation_data["tags"] = [f"tag{i}", f"test{i}", "bulk"]
        
        operations.append(operation_data)
    
    return operations

def save_test_requests(filename: str, data: Any, test_type: str = "general") -> str:
    """
    Save test data to a JSON file
    
    Args:
        filename: Name of the file to save
        data: Data to save
        test_type: Type of test data for organization
    
    Returns:
        Path to the saved file
    """
    # Create test data directory structure
    test_data_dir = Path("tests/test_data") / test_type
    test_data_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = test_data_dir / filename
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"✅ Test data saved to: {file_path}")
    return str(file_path)

def generate_comprehensive_test_suite(pond_id: int = 1) -> Dict[str, str]:
    """
    Generate a comprehensive test suite with all types of test data
    
    Args:
        pond_id: ID of the pond to generate data for
    
    Returns:
        Dictionary mapping test type to file path
    """
    print("🚀 Generating comprehensive test suite...")
    
    # Generate different types of test data
    sensor_data = generate_sensor_data(pond_id, count=50)
    user_data = generate_user_data(count=10)
    pond_data = generate_pond_data(count=5)
    media_data = generate_media_asset_data(pond_id, count=20)
    bulk_ops = generate_bulk_operations(count=15)
    
    # Save all test data
    test_files = {}
    
    test_files["sensor_data"] = save_test_requests(
        "sensor_data_comprehensive.json", 
        sensor_data, 
        "sensor"
    )
    
    test_files["user_data"] = save_test_requests(
        "user_data_comprehensive.json", 
        user_data, 
        "user"
    )
    
    test_files["pond_data"] = save_test_requests(
        "pond_data_comprehensive.json", 
        pond_data, 
        "pond"
    )
    
    test_files["media_data"] = save_test_requests(
        "media_data_comprehensive.json", 
        media_data, 
        "media"
    )
    
    test_files["bulk_operations"] = save_test_requests(
        "bulk_operations_comprehensive.json", 
        bulk_ops, 
        "bulk"
    )
    
    print("✅ Comprehensive test suite generated successfully!")
    return test_files

def generate_stress_test_data(pond_id: int = 1, count: int = 1000) -> str:
    """
    Generate large volume of test data for stress testing
    
    Args:
        pond_id: ID of the pond
        count: Number of sensor readings to generate
    
    Returns:
        Path to the saved file
    """
    print(f"🔥 Generating stress test data ({count} records)...")
    
    # Generate sensor data with high frequency
    sensor_data = []
    base_time = datetime.now()
    
    for i in range(count):
        # Generate data every minute for the last N minutes
        timestamp = base_time - timedelta(minutes=i)
        
        sensor_type = random.choice(['temperature', 'oxygen', 'ph', 'salinity', 'ammonia'])
        
        # Add some realistic patterns (daily cycles, etc.)
        hour = timestamp.hour
        if sensor_type == 'temperature':
            # Temperature varies by hour (colder at night, warmer during day)
            base_temp = 25 + 5 * (hour - 12) / 12  # 20-30°C range
            value = base_temp + random.uniform(-2, 2)
        elif sensor_type == 'oxygen':
            # Oxygen lower at night
            base_oxygen = 6 if 6 <= hour <= 18 else 4
            value = base_oxygen + random.uniform(-1, 1)
        else:
            # Other sensors have random variation
            value = random.uniform(0, 100)
        
        sensor_data.append({
            "pond_id": pond_id,
            "sensor_type": sensor_type,
            "value": round(value, 2),
            "timestamp": timestamp.isoformat(),
            "location": random.choice(["surface", "middle", "bottom"]),
            "notes": f"Stress test data #{i+1}"
        })
    
    file_path = save_test_requests(
        f"stress_test_{count}_records.json", 
        sensor_data, 
        "stress"
    )
    
    print(f"✅ Stress test data generated: {len(sensor_data)} records")
    return file_path

if __name__ == "__main__":
    # Example usage
    print("🧪 Test Request Generator Utility")
    print("=" * 50)
    
    # Generate comprehensive test suite
    test_files = generate_comprehensive_test_suite()
    
    print("\n📁 Generated test files:")
    for test_type, file_path in test_files.items():
        print(f"  {test_type}: {file_path}")
    
    # Generate stress test data
    stress_file = generate_stress_test_data(count=1000)
    print(f"\n🔥 Stress test file: {stress_file}")
    
    print("\n✅ All test data generated successfully!")
