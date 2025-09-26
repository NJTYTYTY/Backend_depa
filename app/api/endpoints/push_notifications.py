"""
Push Notification endpoints for Backend_PWA
"""

from fastapi import APIRouter, Depends, HTTPException, status, Header
from typing import List, Optional
import logging

from ...core.push_service import push_service
from ...core.security import verify_token
from ...storage.push_subscription_storage import push_subscription_storage
from ...schemas.push_notification import (
    PushSubscriptionCreate,
    PushSubscriptionResponse,
    PushMessageRequest,
    PushMessageResponse
)
from ...schemas.alert import AlertCreateRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/push", tags=["push-notifications"])

# Helper function for authentication
async def get_current_user_id(authorization: str = Header(None)) -> int:
    """Get current user ID from token"""
    try:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header required"
            )
        
        token = authorization.split(" ")[1]
        payload = verify_token(token, "access")
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        return int(user_id)
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )


@router.get("/vapid-keys")
async def get_vapid_keys():
    """Get VAPID public key for client-side push subscription"""
    try:
        # Only return public key for security
        public_key = push_service.get_vapid_public_key()
        return {"public_key": public_key}
    except Exception as e:
        logger.error(f"Error getting VAPID keys: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get VAPID keys"
        )


@router.post("/subscribe", response_model=PushSubscriptionResponse)
async def subscribe_to_push(
    subscription_data: PushSubscriptionCreate,
    user_id: int = Depends(get_current_user_id)
):
    """Subscribe to push notifications"""
    try:
        # Convert to PushSubscription
        from ...schemas.push_notification import PushSubscription
        push_subscription = PushSubscription(
            endpoint=subscription_data.endpoint,
            keys=subscription_data.keys,
            user_agent=subscription_data.user_agent
        )
        
        # Create subscription
        subscription = push_subscription_storage.create_subscription(
            user_id=user_id,
            subscription_data=push_subscription
        )
        
        logger.info(f"User {user_id} subscribed to push notifications")
        return subscription
        
    except Exception as e:
        logger.error(f"Error subscribing user {user_id} to push: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to subscribe to push notifications"
        )


@router.get("/subscriptions", response_model=List[PushSubscriptionResponse])
async def get_user_subscriptions(user_id: int = Depends(get_current_user_id)):
    """Get user's push subscriptions"""
    try:
        subscriptions = push_subscription_storage.get_subscriptions_by_user(user_id)
        return subscriptions
    except Exception as e:
        logger.error(f"Error getting subscriptions for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get subscriptions"
        )




@router.post("/send", response_model=PushMessageResponse)
async def send_push_message(
    message_request: PushMessageRequest,
    user_id: int = Depends(get_current_user_id)
):
    """Send push message to a specific user (admin only)"""
    try:
        # Check if user is admin (you can implement admin check here)
        # For now, allow all authenticated users to send messages
        
        from ...schemas.push_notification import PushMessage
        
        # ตรวจสอบว่าเป็น shrimp alert หรือไม่
        is_shrimp_alert = (
            message_request.tag == "shrimp-alert" or 
            "กุ้งลอย" in message_request.title or 
            "shrimp" in message_request.title.lower()
        )
        
        # ถ้าเป็น shrimp alert ให้ใช้หัวข้อและข้อมูลเฉพาะ
        if is_shrimp_alert:
            push_message = PushMessage(
                title="พบกุ้งลอยบนผิวน้ำ!!!",
                body=message_request.body or "ตรวจพบกุ้งลอยบนผิวน้ำ ควรตรวจสอบทันที",
                icon=message_request.icon or "/icons/icon-192x192.png",
                badge=message_request.badge or "/icons/icon-72x72.png",
                image=message_request.image,  # รูปภาพที่ส่งมา
                url=message_request.url,  # URL ที่จะเปิดเมื่อคลิก
                tag="shrimp-alert",
                data={
                    "alert_type": "shrimp_floating",
                    "pond_id": message_request.data.get("pond_id") if message_request.data else None,
                    "timestamp": message_request.data.get("timestamp") if message_request.data else None,
                    **message_request.data  # รวมข้อมูลอื่นๆ ที่ส่งมา
                },
                require_interaction=True,  # บังคับให้ผู้ใช้โต้ตอบ
                silent=False,
                vibrate=[200, 100, 200, 100, 200],  # แบบการสั่น
                actions=[
                    {
                        "action": "view",
                        "title": "ดู",
                        "icon": "/icons/icon-72x72.png"
                    },
                    {
                        "action": "close",
                        "title": "ปิด",
                        "icon": "/icons/icon-72x72.png"
                    }
                ]
            )
        else:
            # สำหรับ notification ปกติ
            push_message = PushMessage(
                title=message_request.title,
                body=message_request.body,
                icon=message_request.icon,
                badge=message_request.badge,
                image=message_request.image,
                url=message_request.url,
                tag=message_request.tag,
                data=message_request.data,
                require_interaction=message_request.require_interaction,
                silent=message_request.silent,
                vibrate=message_request.vibrate,
                actions=message_request.actions
            )
        
        # ถ้ามี alert_type ในข้อมูล ให้สร้าง alert ใน storage ก่อน
        alert_created = False
        if message_request.data and message_request.data.get("alert_type"):
            try:
                alert_data = {
                    "alert_type": message_request.data.get("alert_type"),
                    "pond_id": int(message_request.data.get("pond_id", 0)),
                    "user_id": message_request.user_id,
                    "title": push_message.title,
                    "body": push_message.body,
                    "severity": "high" if "กุ้งลอย" in push_message.title or "shrimp" in push_message.title.lower() else "medium",
                    "image_url": push_message.image,
                    "target_url": push_message.url,
                    "data": push_message.data
                }
                
                # สร้าง alert ใน storage
                from ...storage.alert_storage import AlertStorage
                created_alert = AlertStorage.create_alert(alert_data)
                
                if created_alert:
                    logger.info(f"Alert created in storage: {created_alert['id']}")
                    alert_created = True
                else:
                    logger.warning("Failed to create alert in storage")
                    
            except Exception as e:
                logger.error(f"Error creating alert in storage: {e}")
        
        # Send push message
        result = push_service.send_push_to_user(message_request.user_id, push_message)
        
        # ถ้า push notification ล้มเหลวแต่ alert สร้างสำเร็จ ให้ปรับ result
        if not result.success and alert_created:
            logger.info("Push notification failed but alert created successfully")
            result.message = f"Alert created in storage. {result.message}"
        
        logger.info(f"Push message sent to user {message_request.user_id} by user {user_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error sending push message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send push message"
        )



@router.delete("/cleanup-all")
async def cleanup_all_subscriptions_endpoint(
    user_id: int = Depends(get_current_user_id)
):
    """Clean up ALL subscriptions (for testing/admin purposes)"""
    try:
        logger.info(f"Cleanup ALL request by user {user_id}")
        
        # Direct call to cleanup all
        cleaned_count = push_subscription_storage.cleanup_all_subscriptions()
        
        logger.info(f"Cleaned up ALL {cleaned_count} subscriptions by user {user_id}")
        return {
            "message": f"Cleaned up ALL {cleaned_count} subscriptions",
            "cleaned_count": cleaned_count
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up all subscriptions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cleanup all subscriptions"
        )

@router.post("/send-alert", response_model=PushMessageResponse)
async def send_alert_notification(
    alert_request: AlertCreateRequest,
    user_id: int = Depends(get_current_user_id)
):
    """Send alert notification to specific user"""
    try:
        logger.info(f"Sending alert notification for user {user_id}")
        
        # Convert AlertCreateRequest to dict
        alert_data = {
            "alert_type": alert_request.alert_type,
            "pond_id": alert_request.pond_id,
            "user_id": alert_request.user_id,
            "title": alert_request.title,
            "body": alert_request.body,
            "severity": alert_request.severity.value,
            "image_url": alert_request.image_url,
            "target_url": alert_request.target_url,
            "data": alert_request.data
        }
        
        # Send alert notification
        result = push_service.send_alert_notification(alert_data)
        
        logger.info(f"Alert notification sent: {result.message}")
        return result
        
    except Exception as e:
        logger.error(f"Error sending alert notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send alert notification: {str(e)}"
        )

@router.post("/send-pond-alert", response_model=PushMessageResponse)
async def send_pond_alert_notification(
    alert_request: AlertCreateRequest,
    user_id: int = Depends(get_current_user_id)
):
    """Send alert notification to all users monitoring a pond"""
    try:
        logger.info(f"Sending pond alert notification for pond {alert_request.pond_id}")
        
        # Convert AlertCreateRequest to dict
        alert_data = {
            "alert_type": alert_request.alert_type,
            "pond_id": alert_request.pond_id,
            "user_id": alert_request.user_id,
            "title": alert_request.title,
            "body": alert_request.body,
            "severity": alert_request.severity.value,
            "image_url": alert_request.image_url,
            "target_url": alert_request.target_url,
            "data": alert_request.data
        }
        
        # Send alert to pond users
        result = push_service.send_alert_to_pond_users(alert_data)
        
        logger.info(f"Pond alert notification sent: {result.message}")
        return result
        
    except Exception as e:
        logger.error(f"Error sending pond alert notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send pond alert notification: {str(e)}"
        )










