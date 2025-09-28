"""
Routine settings storage for managing automated lift schedules
"""

import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class RoutineStorage:
    def __init__(self, data_file: str = "data/routine_settings.json"):
        self.data_file = data_file
        self.ensure_data_file()
    
    def ensure_data_file(self):
        """Ensure the data file exists with proper structure"""
        if not os.path.exists(self.data_file):
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump({"ponds": {}}, f, ensure_ascii=False, indent=2)
    
    def load_data(self) -> Dict[str, Any]:
        """Load routine settings from JSON file"""
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading routine settings: {e}")
            return {"ponds": {}}
    
    def save_data(self, data: Dict[str, Any]):
        """Save routine settings to JSON file"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving routine settings: {e}")
            raise
    
    def get_pond_routines(self, pond_id: int) -> Dict[str, Any]:
        """Get routine settings for a specific pond"""
        data = self.load_data()
        pond_key = str(pond_id)
        return data.get("ponds", {}).get(pond_key, {
            "enabled": False,
            "schedules": []
        })
    
    def save_pond_routines(self, pond_id: int, routines: Dict[str, Any]):
        """Save routine settings for a specific pond"""
        data = self.load_data()
        pond_key = str(pond_id)
        
        if "ponds" not in data:
            data["ponds"] = {}
        
        data["ponds"][pond_key] = routines
        self.save_data(data)
    
    def add_schedule(self, pond_id: int, schedule: Dict[str, Any]) -> str:
        """Add a new schedule to a pond's routines"""
        routines = self.get_pond_routines(pond_id)
        
        # Generate unique ID
        schedule_id = f"{pond_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        schedule["id"] = schedule_id
        
        if "schedules" not in routines:
            routines["schedules"] = []
        
        routines["schedules"].append(schedule)
        self.save_pond_routines(pond_id, routines)
        
        return schedule_id
    
    def remove_schedule(self, pond_id: int, schedule_id: str) -> bool:
        """Remove a schedule from a pond's routines"""
        routines = self.get_pond_routines(pond_id)
        
        if "schedules" not in routines:
            return False
        
        original_length = len(routines["schedules"])
        routines["schedules"] = [s for s in routines["schedules"] if s.get("id") != schedule_id]
        
        if len(routines["schedules"]) < original_length:
            self.save_pond_routines(pond_id, routines)
            return True
        
        return False
    
    def update_schedule(self, pond_id: int, schedule_id: str, updated_schedule: Dict[str, Any]) -> bool:
        """Update an existing schedule"""
        routines = self.get_pond_routines(pond_id)
        
        if "schedules" not in routines:
            return False
        
        for i, schedule in enumerate(routines["schedules"]):
            if schedule.get("id") == schedule_id:
                routines["schedules"][i] = {**schedule, **updated_schedule, "id": schedule_id}
                self.save_pond_routines(pond_id, routines)
                return True
        
        return False
    
    def toggle_routine_enabled(self, pond_id: int, enabled: bool) -> bool:
        """Toggle routine enabled status for a pond"""
        routines = self.get_pond_routines(pond_id)
        routines["enabled"] = enabled
        self.save_pond_routines(pond_id, routines)
        return True
    
    def get_all_enabled_schedules(self) -> List[Dict[str, Any]]:
        """Get all enabled schedules from all ponds"""
        data = self.load_data()
        all_schedules = []
        
        for pond_id, pond_data in data.get("ponds", {}).items():
            if pond_data.get("enabled", False):
                for schedule in pond_data.get("schedules", []):
                    schedule_with_pond = {**schedule, "pond_id": int(pond_id)}
                    all_schedules.append(schedule_with_pond)
        
        return all_schedules
