"""
Graph data storage operations
"""

import json
import logging
import os
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime, timedelta

# Storage directory - use absolute path for Railway deployment
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "data"))
try:
    STORAGE_DIR.mkdir(exist_ok=True)
except Exception as e:
    logging.warning(f"Could not create storage directory {STORAGE_DIR}: {e}")
    # Fallback to current directory
    STORAGE_DIR = Path(".")

class GraphDataStorage:
    """Graph data storage operations"""
    
    def __init__(self):
        self.data_file = STORAGE_DIR / "graph_data.json"
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
    
    def get_all(self) -> List[Dict[str, Any]]:
        """Get all graph data"""
        try:
            if self.data_file.exists():
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logging.error(f"Error reading graph data: {e}")
            return []
    
    def get_by_pond(self, pond_id: int) -> List[Dict[str, Any]]:
        """Get graph data for a specific pond"""
        all_data = self.get_all()
        filtered_data = [item for item in all_data if item.get('pond_id') == pond_id]
        logging.info(f"GraphDataStorage: Found {len(all_data)} total batches, {len(filtered_data)} for pond {pond_id}")
        return filtered_data
    
    def get_latest_batch(self, pond_id: int) -> Dict[str, Any]:
        """Get the latest graph data batch for a pond"""
        pond_data = self.get_by_pond(pond_id)
        if pond_data:
            # Sort by timestamp and return the latest
            pond_data.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return pond_data[0]
        return {}
    
    def get_batches_by_time_range(self, pond_id: int, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get graph data batches for a pond within a specific time range"""
        all_data = self.get_all()
        pond_data = [item for item in all_data if item.get('pond_id') == pond_id]
        
        filtered_data = []
        for item in pond_data:
            try:
                timestamp_str = item.get('timestamp', '')
                if timestamp_str:
                    if timestamp_str.endswith('Z'):
                        item_timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    else:
                        item_timestamp = datetime.fromisoformat(timestamp_str)
                    
                    if start_time <= item_timestamp <= end_time:
                        filtered_data.append(item)
            except (ValueError, TypeError) as e:
                logging.warning(f"Error parsing timestamp for graph item {item.get('id', 'unknown')}: {e}")
                continue
        
        # Sort by timestamp (oldest first)
        filtered_data.sort(key=lambda x: x.get('timestamp', ''))
        return filtered_data
    
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new graph data entry"""
        try:
            all_data = self.get_all()
            all_data.append(data)
            
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(all_data, f, indent=2, ensure_ascii=False)
            
            logging.info(f"Created graph data entry: {data.get('id', 'unknown')}")
            return data
        except Exception as e:
            logging.error(f"Error creating graph data: {e}")
            return {}
    
    def clear_all(self) -> bool:
        """Clear all graph data"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump([], f, indent=2, ensure_ascii=False)
            logging.info("Cleared all graph data")
            return True
        except Exception as e:
            logging.error(f"Error clearing graph data: {e}")
            return False
    
    def clear_by_pond(self, pond_id: int) -> bool:
        """Clear graph data for a specific pond"""
        try:
            all_data = self.get_all()
            filtered_data = [item for item in all_data if item.get('pond_id') != pond_id]
            
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(filtered_data, f, indent=2, ensure_ascii=False)
            
            logging.info(f"Cleared graph data for pond {pond_id}")
            return True
        except Exception as e:
            logging.error(f"Error clearing graph data for pond {pond_id}: {e}")
            return False
