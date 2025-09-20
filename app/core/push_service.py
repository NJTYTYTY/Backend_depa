"""
Push Notification Service for Backend_PWA
Handles VAPID key management and push message sending
"""

import os
import json
import base64
from typing import Dict, List, Optional, Any, Tuple
from pywebpush import webpush, WebPushException
from ..schemas.push_notification import PushMessage, PushMessageResponse, VAPIDKeys
from ..storage.push_subscription_storage import push_subscription_storage
import logging

logger = logging.getLogger(__name__)


class PushService:
    """Service class for handling push notifications"""
    
    def __init__(self):
        self.vapid_public_key = None
        self.vapid_private_key = None
        self.vapid_email = None
        self.web_push = None
        self._initialize_vapid_keys()
    
    def _initialize_vapid_keys(self):
        """Initialize VAPID keys from JSON file or generate new ones"""
        try:
            # Try to load from JSON file first (for demo purposes)
            json_file_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "vapid_keys.json")
            if os.path.exists(json_file_path):
                with open(json_file_path, 'r') as f:
                    vapid_data = json.load(f)
                    self.vapid_public_key = vapid_data.get("public_key")
                    self.vapid_private_key = vapid_data.get("private_key")
                    self.vapid_email = vapid_data.get("email", "admin@shrimpsense.com")
                    logger.info("VAPID keys loaded from JSON file")
                    self._setup_web_push()
                    return
            
            # If no JSON file, generate new keys
            logger.warning("VAPID keys JSON file not found. Generating new keys...")
            self._generate_vapid_keys()
                
        except Exception as e:
            logger.error(f"Failed to initialize VAPID keys: {e}")
            self._generate_vapid_keys()
    
    def _generate_vapid_keys(self):
        """Generate new VAPID keys using cryptography directly"""
        try:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric import ec
            from cryptography.hazmat.backends import default_backend
            
            # Generate EC private key
            private_key = ec.generate_private_key(
                ec.SECP256R1(),
                default_backend()
            )
            
            # Get public key
            public_key = private_key.public_key()
            
            # Convert public key to uncompressed point format
            public_key_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.X962,
                format=serialization.PublicFormat.UncompressedPoint
            )
            
            # Convert to URL-safe base64
            self.vapid_public_key = base64.urlsafe_b64encode(public_key_bytes).decode('utf-8').rstrip('=')
            
            # Convert private key to DER format
            private_key_der = private_key.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            # Convert to URL-safe base64
            self.vapid_private_key = base64.urlsafe_b64encode(private_key_der).decode('utf-8').rstrip('=')
            self.vapid_email = "admin@shrimpsense.com"
            
            logger.info("Generated new VAPID keys")
            logger.warning(f"VAPID Public Key: {self.vapid_public_key}")
            logger.warning(f"VAPID Private Key: {self.vapid_private_key}")
            logger.warning("Please save these keys to your environment variables!")
            
            self._setup_web_push()
            
        except Exception as e:
            logger.error(f"Failed to generate VAPID keys: {e}")
            raise
    
    def _setup_web_push(self):
        """Setup WebPush instance with VAPID keys"""
        try:
            # pywebpush doesn't need a WebPush instance, we'll use it directly
            self.web_push = True  # Just mark as available
            logger.info("WebPush service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to setup WebPush: {e}")
            raise
    
    def get_vapid_public_key(self) -> str:
        """Get VAPID public key for client"""
        if not self.vapid_public_key:
            self._initialize_vapid_keys()
        
        # Return the string directly (already converted in _generate_vapid_keys)
        return str(self.vapid_public_key)
    
    def get_vapid_keys(self) -> VAPIDKeys:
        """Get VAPID keys"""
        return VAPIDKeys(
            public_key=self.get_vapid_public_key(),
            private_key=self.vapid_private_key,
            email=self.vapid_email
        )
    
    def send_push_message(self, subscription: Dict[str, Any], message: PushMessage) -> Tuple[bool, str]:
        """Send push message to a single subscription"""
        try:
            if not self.web_push:
                self._setup_web_push()
            
            # Prepare push payload
            payload = {
                "title": message.title,
                "body": message.body,
                "icon": message.icon,
                "badge": message.badge,
                "image": message.image,
                "url": message.url,
                "tag": message.tag,
                "data": message.data,
                "requireInteraction": message.require_interaction,
                "silent": message.silent,
                "vibrate": message.vibrate,
                "actions": message.actions
            }
            
            # Remove None values
            payload = {k: v for k, v in payload.items() if v is not None}
            
            # Send push notification using pywebpush
            response = webpush(
                subscription_info=subscription,
                data=json.dumps(payload),
                vapid_private_key=self.vapid_private_key,
                    vapid_claims={"sub": f"mailto:{self.vapid_email}"},
                ttl=86400,  # 24 hours TTL
                content_encoding="aes128gcm"
            )
            
            logger.info(f"Push message sent successfully: {response.status_code}")
            return True, "Push message sent successfully"
            
        except WebPushException as e:
            logger.error(f"WebPush error: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
            return False, f"WebPush error: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error sending push message: {e}")
            return False, f"Unexpected error: {str(e)}"
    
    def send_push_to_user(self, user_id: int, message: PushMessage) -> PushMessageResponse:
        """Send push message to all subscriptions of a user"""
        try:
            # Get user's subscriptions
            subscriptions = push_subscription_storage.get_subscriptions_by_user(user_id)
            
            if not subscriptions:
                return PushMessageResponse(
                    success=False,
                    message=f"No active subscriptions found for user {user_id}",
                    sent_count=0,
                    failed_count=0
                )
            
            # Get user's notification settings
            user_settings = push_subscription_storage.get_user_settings(user_id)
            if not user_settings:
                user_settings = push_subscription_storage.create_user_settings(user_id)
            
            # Check if user has enabled this type of notification
            if not self._should_send_notification(user_settings, message):
                return PushMessageResponse(
                    success=True,
                    message="Notification blocked by user settings",
                    sent_count=0,
                    failed_count=0
                )
            
            sent_count = 0
            failed_count = 0
            errors = []
            
            # Send to each subscription
            for subscription in subscriptions:
                subscription_data = {
                    "endpoint": subscription.endpoint,
                    "keys": subscription.keys
                }
                
                success, error_msg = self.send_push_message(subscription_data, message)
                
                if success:
                    sent_count += 1
                else:
                    failed_count += 1
                    errors.append(f"Subscription {subscription.id}: {error_msg}")
            
            return PushMessageResponse(
                success=sent_count > 0,
                message=f"Sent {sent_count} notifications, {failed_count} failed",
                sent_count=sent_count,
                failed_count=failed_count,
                errors=errors if errors else None
            )
            
        except Exception as e:
            logger.error(f"Error sending push to user {user_id}: {e}")
            return PushMessageResponse(
                success=False,
                message=f"Error sending push to user: {str(e)}",
                sent_count=0,
                failed_count=0,
                errors=[str(e)]
            )
    
    def send_push_to_all_users(self, message: PushMessage) -> PushMessageResponse:
        """Send push message to all users with active subscriptions"""
        try:
            # Get all subscriptions
            subscriptions = push_subscription_storage.get_all_subscriptions()
            
            if not subscriptions:
                return PushMessageResponse(
                    success=False,
                    message="No active subscriptions found",
                    sent_count=0,
                    failed_count=0
                )
            
            sent_count = 0
            failed_count = 0
            errors = []
            
            # Group subscriptions by user
            user_subscriptions = {}
            for subscription in subscriptions:
                user_id = subscription.user_id
                if user_id not in user_subscriptions:
                    user_subscriptions[user_id] = []
                user_subscriptions[user_id].append(subscription)
            
            # Send to each user
            for user_id, user_subs in user_subscriptions.items():
                # Get user's notification settings
                user_settings = push_subscription_storage.get_user_settings(user_id)
                if not user_settings:
                    user_settings = push_subscription_storage.create_user_settings(user_id)
                
                # Check if user has enabled this type of notification
                if not self._should_send_notification(user_settings, message):
                    continue
                
                # Send to each subscription of this user
                for subscription in user_subs:
                    subscription_data = {
                        "endpoint": subscription.endpoint,
                        "keys": subscription.keys
                    }
                    
                    success, error_msg = self.send_push_message(subscription_data, message)
                    
                    if success:
                        sent_count += 1
                    else:
                        failed_count += 1
                        errors.append(f"User {user_id}, Subscription {subscription.id}: {error_msg}")
            
            return PushMessageResponse(
                success=sent_count > 0,
                message=f"Sent {sent_count} notifications, {failed_count} failed",
                sent_count=sent_count,
                failed_count=failed_count,
                errors=errors if errors else None
            )
            
        except Exception as e:
            logger.error(f"Error sending push to all users: {e}")
            return PushMessageResponse(
                success=False,
                message=f"Error sending push to all users: {str(e)}",
                sent_count=0,
                failed_count=0,
                errors=[str(e)]
            )
    
    def _should_send_notification(self, user_settings, message: PushMessage) -> bool:
        """Check if notification should be sent based on user settings"""
        if not user_settings:
            return True  # Default to sending if no settings
        
        # Check notification type based on message tag or data
        tag = message.tag or ""
        data = message.data or {}
        
        # Sensor alerts
        if "sensor" in tag.lower() or "alert" in tag.lower():
            return user_settings.sensor_alerts
        
        # Pond updates
        if "pond" in tag.lower() or "update" in tag.lower():
            return user_settings.pond_updates
        
        # System notifications
        if "system" in tag.lower() or "maintenance" in tag.lower():
            return user_settings.system_notifications
        
        # Maintenance alerts
        if "maintenance" in tag.lower():
            return user_settings.maintenance_alerts
        
        # Default to system notifications setting
        return user_settings.system_notifications
    
    def cleanup_expired_subscriptions(self, days_old: int = 30) -> int:
        """Clean up expired subscriptions"""
        try:
            return push_subscription_storage.cleanup_inactive_subscriptions(days_old)
        except Exception as e:
            logger.error(f"Error cleaning up subscriptions: {e}")
            return 0
    
    def cleanup_all_subscriptions(self) -> int:
        """Clean up ALL subscriptions (for testing purposes)"""
        try:
            return push_subscription_storage.cleanup_all_subscriptions()
        except Exception as e:
            logger.error(f"Error cleaning up all subscriptions: {e}")
            return 0
    
    def get_service_stats(self) -> Dict[str, Any]:
        """Get push service statistics"""
        try:
            total_subscriptions = push_subscription_storage.count_subscriptions()
            
            return {
                "total_subscriptions": total_subscriptions,
                "vapid_public_key": self.get_vapid_public_key(),
                "service_status": "active" if self.web_push else "inactive"
            }
        except Exception as e:
            logger.error(f"Error getting service stats: {e}")
            return {
                "total_subscriptions": 0,
                "vapid_public_key": None,
                "service_status": "error",
                "error": str(e)
            }


# Global instance
push_service = PushService()
