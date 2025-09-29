"""
ShrimpSize Graph Data Storage
Manages shrimp size data for graph visualization
"""

import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Storage directory - use absolute path for Railway deployment
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "data"))
try:
    STORAGE_DIR.mkdir(exist_ok=True)
except Exception as e:
    logging.warning(f"Could not create storage directory {STORAGE_DIR}: {e}")
    # Fallback to current directory
    STORAGE_DIR = Path(".")

class ShrimpSizeStorage:
    def __init__(self):
        self.data_file = STORAGE_DIR / "graph_shrimpsize.json"
        self.ensure_data_file_exists()
    
    def ensure_data_file_exists(self):
        """Ensure the data file exists, create if it doesn't"""
        if not self.data_file.exists():
            self.data_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
    
    def load_data(self) -> List[Dict[str, Any]]:
        """Load data from JSON file"""
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading shrimp size data: {e}")
            return []
    
    def save_data(self, data: List[Dict[str, Any]]):
        """Save data to JSON file"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving shrimp size data: {e}")
            raise
    
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new shrimp size data entry"""
        try:
            # Load existing data
            all_data = self.load_data()
            
            # Add new entry
            all_data.append(data)
            
            # Save updated data
            self.save_data(all_data)
            
            logger.info(f"Created shrimp size data entry: {data.get('id', 'unknown')}")
            return data
            
        except Exception as e:
            logger.error(f"Error creating shrimp size data: {e}")
            raise
    
    def get_by_pond(self, pond_id: int) -> List[Dict[str, Any]]:
        """Get all shrimp size data for a specific pond"""
        try:
            all_data = self.load_data()
            return [entry for entry in all_data if entry.get('pond_id') == pond_id]
        except Exception as e:
            logger.error(f"Error getting shrimp size data for pond {pond_id}: {e}")
            return []
    
    def get_latest_batch(self, pond_id: int) -> Optional[Dict[str, Any]]:
        """Get the latest shrimp size data batch for a specific pond"""
        try:
            pond_data = self.get_by_pond(pond_id)
            if not pond_data:
                return None
            
            # Sort by timestamp and get the latest
            pond_data.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return pond_data[0] if pond_data else None
            
        except Exception as e:
            logger.error(f"Error getting latest shrimp size batch for pond {pond_id}: {e}")
            return None
    
    def get_by_timeframe(self, pond_id: int, hours: int = 24, timeframe: str = "1D") -> List[Dict[str, Any]]:
        """Get shrimp size data for a specific pond within a timeframe"""
        try:
            pond_data = self.get_by_pond(pond_id)
            if not pond_data:
                return []
            
            # Calculate cutoff time based on timeframe
            now = datetime.now().replace(tzinfo=None)
            if timeframe == "1D":
                # For 1D, get data from today (00:00 to now)
                cutoff_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif timeframe == "7D":
                # For 7D, get data from last 7 days
                cutoff_time = now - timedelta(days=7)
            elif timeframe == "30D":
                # For 30D, get data from last 30 days
                cutoff_time = now - timedelta(days=30)
            else:
                # Default to hours-based filtering
                cutoff_time = now - timedelta(hours=hours)
            
            filtered_data = []
            
            for entry in pond_data:
                try:
                    timestamp_str = entry.get('timestamp', '')
                    if timestamp_str:
                        if timestamp_str.endswith('Z'):
                            entry_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        else:
                            entry_time = datetime.fromisoformat(timestamp_str)
                        
                        # Convert to timezone-naive for comparison
                        entry_time_naive = entry_time.replace(tzinfo=None)
                        
                        # For 1D timeframe, check if it's today's data
                        if timeframe == "1D":
                            entry_date = entry_time_naive.date()
                            today_date = now.date()
                            if entry_date == today_date:
                                filtered_data.append(entry)
                        else:
                            if entry_time_naive >= cutoff_time:
                                filtered_data.append(entry)
                except Exception as e:
                    logger.warning(f"Error parsing timestamp for entry {entry.get('id', 'unknown')}: {e}")
                    continue
            
            # Sort by timestamp (oldest first)
            filtered_data.sort(key=lambda x: x.get('timestamp', ''))
            return filtered_data
            
        except Exception as e:
            logger.error(f"Error getting shrimp size data by timeframe for pond {pond_id}: {e}")
            return []
    
    def clear_all(self) -> bool:
        """Clear all shrimp size data"""
        try:
            self.save_data([])
            logger.info("Cleared all shrimp size data")
            return True
        except Exception as e:
            logger.error(f"Error clearing shrimp size data: {e}")
            return False
    
    def clear_by_pond(self, pond_id: int) -> bool:
        """Clear shrimp size data for a specific pond"""
        try:
            all_data = self.load_data()
            filtered_data = [entry for entry in all_data if entry.get('pond_id') != pond_id]
            self.save_data(filtered_data)
            logger.info(f"Cleared shrimp size data for pond {pond_id}")
            return True
        except Exception as e:
            logger.error(f"Error clearing shrimp size data for pond {pond_id}: {e}")
            return False
    
    def delete_latest_batch(self, pond_id: int) -> Optional[Dict[str, Any]]:
        """Delete the latest shrimp size data batch for a specific pond"""
        try:
            all_data = self.load_data()
            pond_data = [entry for entry in all_data if entry.get('pond_id') == pond_id]
            
            if not pond_data:
                return None
            
            # Sort by timestamp and get the latest
            pond_data.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            latest_entry = pond_data[0]
            
            # Remove from all_data
            all_data = [entry for entry in all_data if entry.get('id') != latest_entry.get('id')]
            self.save_data(all_data)
            
            logger.info(f"Deleted latest shrimp size batch for pond {pond_id}: {latest_entry.get('id', 'unknown')}")
            return latest_entry
            
        except Exception as e:
            logger.error(f"Error deleting latest shrimp size batch for pond {pond_id}: {e}")
            return None
