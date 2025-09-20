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
        
        # Send push message
        result = push_service.send_push_to_user(message_request.user_id, push_message)
        
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










