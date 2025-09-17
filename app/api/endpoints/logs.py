from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import os
import json
import uuid
from datetime import datetime
from pathlib import Path

router = APIRouter()

# Data models
class LogFileCreate(BaseModel):
    pondId: str

class LogFileResponse(BaseModel):
    id: str
    name: str
    date: str
    size: str
    createdAt: str

class LogFilesResponse(BaseModel):
    logFiles: List[LogFileResponse]

# Storage for log files (in production, use a database)
LOG_FILES_STORAGE = "data/log_files.json"
LOGS_DIRECTORY = "data/logs"

def ensure_directories():
    """Ensure required directories exist"""
    os.makedirs(LOGS_DIRECTORY, exist_ok=True)
    os.makedirs(os.path.dirname(LOG_FILES_STORAGE), exist_ok=True)

def load_log_files() -> dict:
    """Load log files from storage"""
    ensure_directories()
    if os.path.exists(LOG_FILES_STORAGE):
        with open(LOG_FILES_STORAGE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_log_files(data: dict):
    """Save log files to storage"""
    ensure_directories()
    with open(LOG_FILES_STORAGE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def generate_log_content(pond_id: str) -> str:
    """Generate sample log content for a pond"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""Pond Log File - {pond_id}
Generated: {timestamp}

Sensor Readings:
- DO: 6.5 mg/L
- pH: 8.2
- Temperature: 29.5°C
- Shrimp Size: 5 cm
- Water Color: สีเขียว
- Minerals: 0.5 กิโลกรัม

Notes:
- Water quality is good
- Shrimp growth is normal
- No issues detected
"""

@router.get("/logs/{pond_id}", response_model=LogFilesResponse)
async def get_log_files(pond_id: str):
    """Get all log files for a specific pond"""
    try:
        log_data = load_log_files()
        pond_logs = log_data.get(pond_id, [])
        
        # Convert to response format
        log_files = []
        for log in pond_logs:
            log_files.append(LogFileResponse(
                id=log["id"],
                name=log["name"],
                date=log["date"],
                size=log["size"],
                createdAt=log["createdAt"]
            ))
        
        return LogFilesResponse(logFiles=log_files)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading log files: {str(e)}")

@router.post("/logs", response_model=LogFileResponse)
async def create_log_file(log_data: LogFileCreate):
    """Create a new log file for a pond"""
    try:
        ensure_directories()
        
        # Generate unique ID and filename
        log_id = str(uuid.uuid4())
        timestamp = datetime.now()
        filename = f"log_{log_data.pondId}_{timestamp.strftime('%Y%m%d_%H%M%S')}.txt"
        filepath = os.path.join(LOGS_DIRECTORY, filename)
        
        # Generate log content
        content = generate_log_content(log_data.pondId)
        
        # Write file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Get file size
        file_size = os.path.getsize(filepath)
        size_str = f"{file_size / 1024:.1f} KB"
        
        # Create log entry
        log_entry = {
            "id": log_id,
            "name": f"Log File - {timestamp.strftime('%Y-%m-%d')}",
            "date": timestamp.strftime("%Y-%m-%d %H:%M"),
            "size": size_str,
            "createdAt": timestamp.isoformat(),
            "filepath": filepath
        }
        
        # Save to storage
        log_data_storage = load_log_files()
        if log_data.pondId not in log_data_storage:
            log_data_storage[log_data.pondId] = []
        log_data_storage[log_data.pondId].append(log_entry)
        save_log_files(log_data_storage)
        
        return LogFileResponse(
            id=log_entry["id"],
            name=log_entry["name"],
            date=log_entry["date"],
            size=log_entry["size"],
            createdAt=log_entry["createdAt"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating log file: {str(e)}")

@router.delete("/logs/{log_id}")
async def delete_log_file(log_id: str):
    """Delete a specific log file"""
    try:
        log_data = load_log_files()
        
        # Find and remove the log file
        found = False
        for pond_id, logs in log_data.items():
            for i, log in enumerate(logs):
                if log["id"] == log_id:
                    # Delete physical file
                    if os.path.exists(log["filepath"]):
                        os.remove(log["filepath"])
                    
                    # Remove from storage
                    logs.pop(i)
                    found = True
                    break
            if found:
                break
        
        if not found:
            raise HTTPException(status_code=404, detail="Log file not found")
        
        # Save updated data
        save_log_files(log_data)
        
        return {"message": "Log file deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting log file: {str(e)}")

@router.get("/logs/{log_id}/download")
async def download_log_file(log_id: str):
    """Download a specific log file"""
    try:
        log_data = load_log_files()
        
        # Find the log file
        filepath = None
        filename = None
        for pond_id, logs in log_data.items():
            for log in logs:
                if log["id"] == log_id:
                    filepath = log["filepath"]
                    filename = f"{log['name']}.txt"
                    break
            if filepath:
                break
        
        if not filepath or not os.path.exists(filepath):
            raise HTTPException(status_code=404, detail="Log file not found")
        
        return FileResponse(
            path=filepath,
            filename=filename,
            media_type='text/plain'
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error downloading log file: {str(e)}")
