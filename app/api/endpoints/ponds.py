"""
Pond management endpoints for Backend_PWA
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from datetime import datetime

from ...storage import PondStorage, UserStorage
from ...schemas.pond import (
    PondCreate, 
    PondUpdate, 
    PondResponse, 
    PondList, 
    PondFilter,
    PondStats,
    PondDetail
)
from ..dependencies import get_current_active_user, get_admin_user

router = APIRouter(prefix="/ponds", tags=["ponds"])

def verify_pond_ownership(pond_id: int, current_user: dict) -> dict:
    """
    Verify pond ownership and return pond object
    """
    pond = PondStorage.get_by_id(pond_id)
    if not pond:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Pond not found"
        )
    
    # Admin can access all ponds, owners can access their own ponds
    if not current_user["is_admin"] and pond["owner_id"] != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Not authorized to access this pond"
        )
    
    return pond

@router.get("/", response_model=PondList)
async def get_ponds(
    current_user: dict = Depends(get_current_active_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    owner_id: Optional[int] = Query(None)
):
    """
    Get list of ponds for the current user
    """
    if current_user["is_admin"]:
        # Admin can see all ponds
        ponds = PondStorage.get_all()
    else:
        # Regular users can only see their own ponds
        ponds = PondStorage.get_by_owner(current_user["id"])
    
    # Apply filters
    if search:
        ponds = [p for p in ponds if search.lower() in p.get("name", "").lower()]
    
    if owner_id is not None:
        ponds = [p for p in ponds if p.get("owner_id") == owner_id]
    
    # Apply pagination
    total = len(ponds)
    ponds = ponds[skip:skip + limit]
    
    return PondList(
        ponds=[PondResponse(**pond) for pond in ponds],
        total=total,
        skip=skip,
        limit=limit
    )

@router.post("/", response_model=PondResponse)
async def create_pond(
    pond: PondCreate,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Create a new pond
    """
    print(f"🔍 Received pond data: {pond}")
    print(f"🔍 Current user: {current_user}")
    
    pond_data = {
        "name": pond.name,
        "size": pond.size,
        "location": pond.location,
        "notes": pond.notes,
        "date": pond.date,
        "dimensions": pond.dimensions,
        "depth": pond.depth,
        "shrimp_count": pond.shrimp_count,
        "owner_id": current_user["id"]
    }
    
    print(f"🔍 Processed pond_data: {pond_data}")
    
    try:
        created_pond = PondStorage.create(pond_data)
        print(f"✅ Created pond: {created_pond}")
        return PondResponse(**created_pond)
    except Exception as e:
        print(f"❌ Error creating pond: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create pond: {str(e)}"
        )

@router.get("/{pond_id}", response_model=PondDetail)
async def get_pond(
    pond_id: int,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Get pond details by ID
    """
    pond = verify_pond_ownership(pond_id, current_user)
    
    # Get owner information
    owner = UserStorage.get_by_id(pond["owner_id"])
    owner_info = {
        "id": owner["id"],
        "phone_number": owner["phone_number"],
        "email": owner["email"],
        "full_name": owner["full_name"]
    } if owner else None
    
    return PondDetail(
        **pond,
        owner=owner_info
    )

@router.put("/{pond_id}", response_model=PondResponse)
async def update_pond(
    pond_id: int,
    pond_update: PondUpdate,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Update pond information
    """
    verify_pond_ownership(pond_id, current_user)
    
    update_data = pond_update.dict(exclude_unset=True)
    updated_pond = PondStorage.update(pond_id, update_data)
    
    if not updated_pond:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pond not found"
        )
    
    return PondResponse(**updated_pond)

@router.delete("/{pond_id}")
async def delete_pond(
    pond_id: int,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Delete a pond
    """
    verify_pond_ownership(pond_id, current_user)
    
    success = PondStorage.delete(pond_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pond not found"
        )
    
    return {"message": "Pond deleted successfully"}

@router.get("/{pond_id}/stats", response_model=PondStats)
async def get_pond_stats(
    pond_id: int,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Get pond statistics
    """
    pond = verify_pond_ownership(pond_id, current_user)
    
    # For now, return basic stats
    # In a real implementation, you would calculate these from sensor data
    stats = PondStats(
        pond_id=pond_id,
        total_sensor_readings=0,  # Would calculate from sensor readings
        last_sensor_reading=None,  # Would get from latest sensor reading
        media_count=0,  # Would count media assets
        insights_count=0,  # Would count insights
        control_logs_count=0  # Would count control logs
    )
    
    return stats

@router.get("/{pond_id}/media")
async def get_pond_media(
    pond_id: int,
    current_user: dict = Depends(get_current_active_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100)
):
    """
    Get media assets for a pond
    """
    verify_pond_ownership(pond_id, current_user)
    
    # For now, return empty list
    # In a real implementation, you would get from MediaAssetStorage
    return {
        "media": [],
        "total": 0,
        "skip": skip,
        "limit": limit
    }

@router.get("/{pond_id}/readings")
async def get_pond_readings(
    pond_id: int,
    current_user: dict = Depends(get_current_active_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None)
):
    """
    Get sensor readings for a pond
    """
    verify_pond_ownership(pond_id, current_user)
    
    # For now, return empty list
    # In a real implementation, you would get from SensorReadingStorage
    return {
        "readings": [],
        "total": 0,
        "skip": skip,
        "limit": limit
    }

@router.get("/{pond_id}/history")
async def get_pond_history(
    pond_id: int,
    current_user: dict = Depends(get_current_active_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100)
):
    """
    Get pond history (events, insights, control logs)
    """
    verify_pond_ownership(pond_id, current_user)
    
    # For now, return empty list
    # In a real implementation, you would combine data from multiple sources
    return {
        "events": [],
        "total": 0,
        "skip": skip,
        "limit": limit
    }

# Helper function for owner/admin access
async def get_owner_or_admin_user(current_user: dict = Depends(get_current_active_user)) -> dict:
    """
    Get current user who is either owner or admin
    """
    if current_user["is_admin"]:
        return current_user
    
    # Check if user has owner role
    if current_user["role"] == "owner":
        return current_user
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not enough permissions. Owner or admin access required."
    )