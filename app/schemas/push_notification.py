"""
Push Notification schemas for Backend_PWA
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class PushSubscription(BaseModel):
    """Push subscription data from client"""
    endpoint: str = Field(..., description="Push service endpoint URL")
    keys: Dict[str, str] = Field(..., description="Push subscription keys")
    user_agent: Optional[str] = Field(None, description="User agent string")
    created_at: Optional[datetime] = Field(None, description="Subscription creation time")


class PushSubscriptionCreate(BaseModel):
    """Request schema for creating push subscription"""
    endpoint: str = Field(..., description="Push service endpoint URL")
    keys: Dict[str, str] = Field(..., description="Push subscription keys")
    user_agent: Optional[str] = Field(None, description="User agent string")


class PushSubscriptionResponse(BaseModel):
    """Response schema for push subscription"""
    id: str = Field(..., description="Subscription ID")
    user_id: int = Field(..., description="User ID")
    endpoint: str = Field(..., description="Push service endpoint URL")
    keys: Dict[str, str] = Field(..., description="Push subscription keys")
    user_agent: Optional[str] = Field(None, description="User agent string")
    created_at: datetime = Field(..., description="Subscription creation time")
    is_active: bool = Field(True, description="Subscription active status")


class PushMessage(BaseModel):
    """Push message data"""
    title: str = Field(..., description="Notification title")
    body: str = Field(..., description="Notification body")
    icon: Optional[str] = Field(None, description="Notification icon URL")
    badge: Optional[str] = Field(None, description="Notification badge URL")
    image: Optional[str] = Field(None, description="Notification image URL")
    url: Optional[str] = Field(None, description="URL to open when notification is clicked")
    tag: Optional[str] = Field(None, description="Notification tag for grouping")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional data")
    require_interaction: bool = Field(False, description="Require user interaction")
    silent: bool = Field(False, description="Silent notification")
    vibrate: Optional[list] = Field(None, description="Vibration pattern")
    actions: Optional[list] = Field(None, description="Notification actions")


class PushMessageRequest(BaseModel):
    """Request schema for sending push message"""
    user_id: int = Field(..., description="Target user ID")
    title: str = Field(..., description="Notification title")
    body: str = Field(..., description="Notification body")
    icon: Optional[str] = Field(None, description="Notification icon URL")
    badge: Optional[str] = Field(None, description="Notification badge URL")
    image: Optional[str] = Field(None, description="Notification image URL")
    url: Optional[str] = Field(None, description="URL to open when notification is clicked")
    tag: Optional[str] = Field(None, description="Notification tag for grouping")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional data")
    require_interaction: bool = Field(False, description="Require user interaction")
    silent: bool = Field(False, description="Silent notification")
    vibrate: Optional[list] = Field(None, description="Vibration pattern")
    actions: Optional[list] = Field(None, description="Notification actions")


class PushMessageResponse(BaseModel):
    """Response schema for push message sending"""
    success: bool = Field(..., description="Success status")
    message: str = Field(..., description="Response message")
    sent_count: int = Field(0, description="Number of notifications sent")
    failed_count: int = Field(0, description="Number of failed notifications")
    errors: Optional[list] = Field(None, description="Error details")


class VAPIDKeys(BaseModel):
    """VAPID keys for push notifications"""
    public_key: str = Field(..., description="VAPID public key")
    private_key: str = Field(..., description="VAPID private key")
    email: str = Field(..., description="VAPID email")


class PushNotificationSettings(BaseModel):
    """User push notification settings"""
    user_id: int = Field(..., description="User ID")
    sensor_alerts: bool = Field(True, description="Enable sensor alerts")
    pond_updates: bool = Field(True, description="Enable pond updates")
    system_notifications: bool = Field(True, description="Enable system notifications")
    maintenance_alerts: bool = Field(True, description="Enable maintenance alerts")
    created_at: Optional[datetime] = Field(None, description="Settings creation time")
    updated_at: Optional[datetime] = Field(None, description="Settings last update time")


class PushNotificationSettingsUpdate(BaseModel):
    """Request schema for updating push notification settings"""
    sensor_alerts: Optional[bool] = Field(None, description="Enable sensor alerts")
    pond_updates: Optional[bool] = Field(None, description="Enable pond updates")
    system_notifications: Optional[bool] = Field(None, description="Enable system notifications")
    maintenance_alerts: Optional[bool] = Field(None, description="Enable maintenance alerts")
