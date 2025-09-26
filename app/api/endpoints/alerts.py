"""
Alert API endpoints for Shrimp Farm Alert System
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from datetime import datetime
import logging

from ...schemas.alert import (
    AlertData, AlertCreateRequest, AlertUpdateRequest, 
    AlertResponse, AlertListResponse, AlertStatsResponse,
    parse_alert_type
)
from ...storage.alert_storage import AlertStorage
from ..dependencies import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/create", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
async def create_alert(
    alert_request: AlertCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Create a new alert"""
    try:
        # Parse alert type to extract base type and ID
        base_type, alert_id = parse_alert_type(alert_request.alert_type)
        
        # Create alert data
        alert_data = {
            "alert_type": alert_request.alert_type,
            "pond_id": alert_request.pond_id,
            "user_id": alert_request.user_id,
            "title": alert_request.title,
            "body": alert_request.body,
            "status": "unread",
            "severity": alert_request.severity.value,
            "image_url": alert_request.image_url,
            "target_url": alert_request.target_url,
            "data": alert_request.data
        }
        
        # Create alert
        created_alert = AlertStorage.create_alert(alert_data)
        
        if not created_alert:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create alert"
            )
        
        logger.info(f"Created alert {created_alert['id']} for user {alert_request.user_id}")
        
        return AlertResponse(
            success=True,
            message="Alert created successfully",
            data=created_alert
        )
        
    except Exception as e:
        logger.error(f"Error creating alert: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating alert: {str(e)}"
        )

@router.get("/user/{user_id}", response_model=AlertListResponse)
async def get_user_alerts(
    user_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get all alerts for a specific user"""
    try:
        # Check if user can access these alerts
        if not current_user.get("is_admin", False) and current_user.get("id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        alerts = AlertStorage.get_alerts_by_user(user_id)
        unread_count = len([a for a in alerts if a.get('status') == 'unread'])
        
        return AlertListResponse(
            success=True,
            message=f"Retrieved {len(alerts)} alerts for user {user_id}",
            alerts=alerts,
            total_count=len(alerts),
            unread_count=unread_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user alerts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting user alerts: {str(e)}"
        )

@router.get("/pond/{pond_id}", response_model=AlertListResponse)
async def get_pond_alerts(
    pond_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get all alerts for a specific pond"""
    try:
        alerts = AlertStorage.get_alerts_by_pond(pond_id)
        unread_count = len([a for a in alerts if a.get('status') == 'unread'])
        
        return AlertListResponse(
            success=True,
            message=f"Retrieved {len(alerts)} alerts for pond {pond_id}",
            alerts=alerts,
            total_count=len(alerts),
            unread_count=unread_count
        )
        
    except Exception as e:
        logger.error(f"Error getting pond alerts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting pond alerts: {str(e)}"
        )

@router.get("/user/{user_id}/unread", response_model=AlertListResponse)
async def get_user_unread_alerts(
    user_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get unread alerts for a specific user"""
    try:
        # Check if user can access these alerts
        if not current_user.get("is_admin", False) and current_user.get("id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        alerts = AlertStorage.get_unread_alerts_by_user(user_id)
        
        return AlertListResponse(
            success=True,
            message=f"Retrieved {len(alerts)} unread alerts for user {user_id}",
            alerts=alerts,
            total_count=len(alerts),
            unread_count=len(alerts)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user unread alerts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting user unread alerts: {str(e)}"
        )

@router.get("/pond/{pond_id}/unread", response_model=AlertListResponse)
async def get_pond_unread_alerts(
    pond_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get unread alerts for a specific pond"""
    try:
        alerts = AlertStorage.get_unread_alerts_by_pond(pond_id)
        
        return AlertListResponse(
            success=True,
            message=f"Retrieved {len(alerts)} unread alerts for pond {pond_id}",
            alerts=alerts,
            total_count=len(alerts),
            unread_count=len(alerts)
        )
        
    except Exception as e:
        logger.error(f"Error getting pond unread alerts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting pond unread alerts: {str(e)}"
        )

@router.put("/{alert_id}/read", response_model=AlertResponse)
async def mark_alert_as_read(
    alert_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Mark an alert as read"""
    try:
        # Get alert to check ownership
        alert = AlertStorage.get_alert_by_id(alert_id)
        if not alert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found"
            )
        
        # Check if user can modify this alert
        if not current_user.get("is_admin", False) and current_user.get("id") != alert.get("user_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Mark as read
        success = AlertStorage.mark_alert_as_read(alert_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to mark alert as read"
            )
        
        # Get updated alert
        updated_alert = AlertStorage.get_alert_by_id(alert_id)
        
        logger.info(f"Marked alert {alert_id} as read by user {current_user.get('id')}")
        
        return AlertResponse(
            success=True,
            message="Alert marked as read",
            data=updated_alert
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking alert as read: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error marking alert as read: {str(e)}"
        )

@router.put("/{alert_id}/unread", response_model=AlertResponse)
async def mark_alert_as_unread(
    alert_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Mark an alert as unread"""
    try:
        # Get alert to check ownership
        alert = AlertStorage.get_alert_by_id(alert_id)
        if not alert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found"
            )
        
        # Check if user can modify this alert
        if not current_user.get("is_admin", False) and current_user.get("id") != alert.get("user_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Mark as unread
        success = AlertStorage.mark_alert_as_unread(alert_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to mark alert as unread"
            )
        
        # Get updated alert
        updated_alert = AlertStorage.get_alert_by_id(alert_id)
        
        logger.info(f"Marked alert {alert_id} as unread by user {current_user.get('id')}")
        
        return AlertResponse(
            success=True,
            message="Alert marked as unread",
            data=updated_alert
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking alert as unread: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error marking alert as unread: {str(e)}"
        )

@router.get("/user/{user_id}/stats", response_model=AlertStatsResponse)
async def get_user_alert_stats(
    user_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get alert statistics for a user"""
    try:
        # Check if user can access these stats
        if not current_user.get("is_admin", False) and current_user.get("id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        stats = AlertStorage.get_alert_stats_by_user(user_id)
        
        return AlertStatsResponse(
            success=True,
            total_alerts=stats["total_alerts"],
            unread_alerts=stats["unread_alerts"],
            alerts_by_type=stats["alerts_by_type"],
            alerts_by_pond=stats["alerts_by_pond"],
            alerts_by_severity=stats["alerts_by_severity"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user alert stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting user alert stats: {str(e)}"
        )

@router.get("/pond/{pond_id}/badge-count", response_model=dict)
async def get_pond_badge_count(
    pond_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get unread alert count for pond badge"""
    try:
        count = AlertStorage.get_pond_alert_badge_count(pond_id)
        
        return {
            "success": True,
            "pond_id": pond_id,
            "unread_count": count,
            "has_alerts": count > 0
        }
        
    except Exception as e:
        logger.error(f"Error getting pond badge count: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting pond badge count: {str(e)}"
        )

@router.delete("/{alert_id}", response_model=AlertResponse)
async def delete_alert(
    alert_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete an alert"""
    try:
        # Get alert to check ownership
        alert = AlertStorage.get_alert_by_id(alert_id)
        if not alert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found"
            )
        
        # Check if user can delete this alert
        if not current_user.get("is_admin", False) and current_user.get("id") != alert.get("user_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Delete alert
        success = AlertStorage.delete_alert(alert_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete alert"
            )
        
        logger.info(f"Deleted alert {alert_id} by user {current_user.get('id')}")
        
        return AlertResponse(
            success=True,
            message="Alert deleted successfully",
            data=None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting alert: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting alert: {str(e)}"
        )
