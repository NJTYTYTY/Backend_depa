"""
System control endpoints for routine automation
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any, Optional
import json
import os
import asyncio
from datetime import datetime
import logging
import aiohttp
import pytz

router = APIRouter()

# Global system state
system_state = {
    "enabled": False,
    "last_check": None,
    "check_interval": 30,  # seconds
    "background_task": None
}

class SystemToggleRequest(BaseModel):
    action: str  # "on" or "off"

class SystemStatusResponse(BaseModel):
    enabled: bool
    last_check: Optional[str] = None
    status: str

def get_routine_settings_path():
    """Get the path to routine_settings.json"""
    return os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "routine_settings.json")

def load_routine_settings():
    """Load routine settings from JSON file"""
    try:
        settings_path = get_routine_settings_path()
        if os.path.exists(settings_path):
            with open(settings_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logging.error(f"Error loading routine settings: {e}")
        return {}

def is_today_scheduled(pond_id: str, current_time: str, current_day: str):
    """
    Check if today is scheduled for the given pond
    
    Args:
        pond_id: Pond ID as string
        current_time: Current time in HH:MM format
        current_day: Current day in Thai (e.g., "จันทร์", "อังคาร")
    
    Returns:
        bool: True if today is scheduled
    """
    try:
        settings = load_routine_settings()
        ponds = settings.get("ponds", {})
        pond_settings = ponds.get(pond_id, {})
        
        if not pond_settings.get("enabled", False):
            return False
        
        schedules = pond_settings.get("schedules", [])
        
        for schedule in schedules:
            if (schedule.get("time") == current_time and 
                current_day in schedule.get("days", [])):
                return True
        
        return False
    except Exception as e:
        logging.error(f"Error checking schedule for pond {pond_id}: {e}")
        return False

async def check_routine_schedules():
    """
    Background task to check routine schedules every 30 seconds
    """
    while system_state["enabled"]:
        try:
            # Get current time in Bangkok timezone
            bangkok_tz = pytz.timezone('Asia/Bangkok')
            current_time_bangkok = datetime.now(bangkok_tz)
            current_time = current_time_bangkok.strftime("%H:%M")
            current_day = get_thai_day_name(current_time_bangkok.weekday())
            
            logging.info(f"Checking routine schedules at {current_time} on {current_day} (Bangkok time)")
            
            # Check all ponds
            settings = load_routine_settings()
            ponds = settings.get("ponds", {})
            
            for pond_id in ponds.keys():
                if is_today_scheduled(pond_id, current_time, current_day):
                    logging.info(f"Routine scheduled for pond {pond_id} at {current_time} - Triggering lift_up")
                    await trigger_routine_for_pond(pond_id)
            
            system_state["last_check"] = current_time_bangkok.isoformat()
            
        except Exception as e:
            logging.error(f"Error in routine check: {e}")
        
        # Wait 30 seconds before next check
        await asyncio.sleep(system_state["check_interval"])

def get_thai_day_name(weekday: int) -> str:
    """Convert weekday number to Thai day name"""
    days = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"]
    return days[weekday]

async def trigger_routine_for_pond(pond_id: str):
    """
    Trigger routine for specific pond by calling the Railway API
    """
    try:
        # Railway API endpoint
        railway_url = "https://rspi1-production.up.railway.app/api/lift-up"
        
        # Prepare request data
        request_data = {
            "pondId": pond_id,
            "action": "lift_up",
            "timestamp": datetime.now(pytz.timezone('Asia/Bangkok')).isoformat(),
            "source": "automated_routine"
        }
        
        logging.info(f"Triggering routine for pond {pond_id} - Sending POST to {railway_url}")
        logging.info(f"Request data: {request_data}")
        
        # Send POST request to Railway
        async with aiohttp.ClientSession() as session:
            async with session.post(
                railway_url,
                json=request_data,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    logging.info(f"Successfully triggered routine for pond {pond_id}: {result}")
                else:
                    error_text = await response.text()
                    logging.error(f"Failed to trigger routine for pond {pond_id}: {response.status} - {error_text}")
        
    except asyncio.TimeoutError:
        logging.error(f"Timeout when triggering routine for pond {pond_id}")
    except Exception as e:
        logging.error(f"Error triggering routine for pond {pond_id}: {e}")

@router.post("/system/toggle", response_model=SystemStatusResponse)
async def toggle_system(request: SystemToggleRequest):
    """
    Toggle system on/off for routine automation
    
    Args:
        request: SystemToggleRequest with action "on" or "off"
    
    Returns:
        SystemStatusResponse: Current system status
    """
    try:
        if request.action.lower() == "on":
            if not system_state["enabled"]:
                system_state["enabled"] = True
                
                # Start background task if not already running
                if system_state["background_task"] is None or system_state["background_task"].done():
                    system_state["background_task"] = asyncio.create_task(check_routine_schedules())
                    logging.info("System enabled - Background routine checker started")
                else:
                    logging.info("System enabled - Background routine checker already running")
            else:
                logging.info("System is already enabled")
                
        elif request.action.lower() == "off":
            if system_state["enabled"]:
                system_state["enabled"] = False
                
                # Cancel background task
                if system_state["background_task"] and not system_state["background_task"].done():
                    system_state["background_task"].cancel()
                    system_state["background_task"] = None
                    logging.info("System disabled - Background routine checker stopped")
                else:
                    logging.info("System disabled - No background task to stop")
            else:
                logging.info("System is already disabled")
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Action must be 'on' or 'off'"
            )
        
        return SystemStatusResponse(
            enabled=system_state["enabled"],
            last_check=system_state["last_check"],
            status="enabled" if system_state["enabled"] else "disabled"
        )
        
    except Exception as e:
        logging.error(f"Error toggling system: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle system: {str(e)}"
        )

@router.get("/system/status", response_model=SystemStatusResponse)
async def get_system_status():
    """
    Get current system status
    
    Returns:
        SystemStatusResponse: Current system status
    """
    return SystemStatusResponse(
        enabled=system_state["enabled"],
        last_check=system_state["last_check"],
        status="enabled" if system_state["enabled"] else "disabled"
    )

@router.get("/system/routine-settings")
async def get_routine_settings():
    """
    Get current routine settings from JSON file
    
    Returns:
        Dict: Routine settings
    """
    try:
        settings = load_routine_settings()
        return {
            "status": "success",
            "data": settings
        }
    except Exception as e:
        logging.error(f"Error getting routine settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get routine settings: {str(e)}"
        )
