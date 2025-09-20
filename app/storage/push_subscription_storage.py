"""
Push Subscription Storage for Backend_PWA
Handles push subscription data storage using JSON files
"""

import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from ..schemas.push_notification import PushSubscription, PushSubscriptionResponse, PushNotificationSettings


class PushSubscriptionStorage:
    """Storage class for push subscriptions"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.subscriptions_file = os.path.join(data_dir, "push_subscriptions.json")
        self.settings_file = os.path.join(data_dir, "push_notification_settings.json")
        self._ensure_data_dir()
        self._initialize_files()
    
    def _ensure_data_dir(self):
        """Ensure data directory exists"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
    
    def _initialize_files(self):
        """Initialize JSON files if they don't exist"""
        # Initialize subscriptions file
        if not os.path.exists(self.subscriptions_file):
            with open(self.subscriptions_file, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
        
        # Initialize settings file
        if not os.path.exists(self.settings_file):
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
    
    def _load_subscriptions(self) -> Dict[str, Any]:
        """Load subscriptions from JSON file"""
        try:
            with open(self.subscriptions_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_subscriptions(self, data: Dict[str, Any]):
        """Save subscriptions to JSON file"""
        with open(self.subscriptions_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _load_settings(self) -> Dict[str, Any]:
        """Load settings from JSON file"""
        try:
            with open(self.settings_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_settings(self, data: Dict[str, Any]):
        """Save settings to JSON file"""
        with open(self.settings_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def create_subscription(self, user_id: int, subscription_data: PushSubscription) -> PushSubscriptionResponse:
        """Create a new push subscription"""
        subscriptions = self._load_subscriptions()
        
        # Generate unique subscription ID
        subscription_id = str(uuid.uuid4())
        
        # Create subscription record
        subscription_record = {
            "id": subscription_id,
            "user_id": user_id,
            "endpoint": subscription_data.endpoint,
            "keys": subscription_data.keys,
            "user_agent": subscription_data.user_agent,
            "created_at": datetime.utcnow().isoformat(),
            "is_active": True
        }
        
        # Store subscription
        subscriptions[subscription_id] = subscription_record
        self._save_subscriptions(subscriptions)
        
        return PushSubscriptionResponse(**subscription_record)
    
    def get_subscriptions_by_user(self, user_id: int) -> List[PushSubscriptionResponse]:
        """Get all active subscriptions for a user"""
        subscriptions = self._load_subscriptions()
        user_subscriptions = []
        
        for sub_data in subscriptions.values():
            if sub_data.get("user_id") == user_id and sub_data.get("is_active", True):
                user_subscriptions.append(PushSubscriptionResponse(**sub_data))
        
        return user_subscriptions
    
    def get_all_subscriptions(self) -> List[PushSubscriptionResponse]:
        """Get all active subscriptions"""
        subscriptions = self._load_subscriptions()
        all_subscriptions = []
        
        for sub_data in subscriptions.values():
            if sub_data.get("is_active", True):
                all_subscriptions.append(PushSubscriptionResponse(**sub_data))
        
        return all_subscriptions
    
    def get_subscription_by_id(self, subscription_id: str) -> Optional[PushSubscriptionResponse]:
        """Get subscription by ID"""
        subscriptions = self._load_subscriptions()
        sub_data = subscriptions.get(subscription_id)
        
        if sub_data and sub_data.get("is_active", True):
            return PushSubscriptionResponse(**sub_data)
        
        return None
    
    def deactivate_subscription(self, subscription_id: str) -> bool:
        """Deactivate a subscription"""
        subscriptions = self._load_subscriptions()
        
        if subscription_id in subscriptions:
            subscriptions[subscription_id]["is_active"] = False
            subscriptions[subscription_id]["deactivated_at"] = datetime.utcnow().isoformat()
            self._save_subscriptions(subscriptions)
            return True
        
        return False
    
    def delete_subscription(self, subscription_id: str) -> bool:
        """Delete a subscription permanently"""
        subscriptions = self._load_subscriptions()
        
        if subscription_id in subscriptions:
            del subscriptions[subscription_id]
            self._save_subscriptions(subscriptions)
            return True
        
        return False
    
    def cleanup_inactive_subscriptions(self, days_old: int = 30):
        """Clean up inactive subscriptions older than specified days"""
        subscriptions = self._load_subscriptions()
        cutoff_date = datetime.utcnow().timestamp() - (days_old * 24 * 60 * 60)
        cleaned_count = 0
        
        subscriptions_to_remove = []
        for sub_id, sub_data in subscriptions.items():
            if not sub_data.get("is_active", True):
                deactivated_at = sub_data.get("deactivated_at")
                if deactivated_at:
                    deactivated_timestamp = datetime.fromisoformat(deactivated_at).timestamp()
                    if deactivated_timestamp < cutoff_date:
                        subscriptions_to_remove.append(sub_id)
        
        for sub_id in subscriptions_to_remove:
            del subscriptions[sub_id]
            cleaned_count += 1
        
        if cleaned_count > 0:
            self._save_subscriptions(subscriptions)
        
        return cleaned_count
    
    def cleanup_all_subscriptions(self):
        """Clean up ALL subscriptions (for testing purposes)"""
        subscriptions = self._load_subscriptions()
        cleaned_count = len(subscriptions)
        
        print(f"DEBUG: Found {cleaned_count} subscriptions to clean up")
        print(f"DEBUG: Subscriptions before cleanup: {list(subscriptions.keys())}")
        
        # Clear all subscriptions
        self._save_subscriptions({})
        
        print(f"DEBUG: Cleanup completed, removed {cleaned_count} subscriptions")
        return cleaned_count
    
    def get_user_settings(self, user_id: int) -> Optional[PushNotificationSettings]:
        """Get user's push notification settings"""
        settings = self._load_settings()
        user_settings = settings.get(str(user_id))
        
        if user_settings:
            return PushNotificationSettings(**user_settings)
        
        return None
    
    def create_user_settings(self, user_id: int) -> PushNotificationSettings:
        """Create default settings for a user"""
        settings = self._load_settings()
        
        default_settings = {
            "user_id": user_id,
            "sensor_alerts": True,
            "pond_updates": True,
            "system_notifications": True,
            "maintenance_alerts": True,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        settings[str(user_id)] = default_settings
        self._save_settings(settings)
        
        return PushNotificationSettings(**default_settings)
    
    def update_user_settings(self, user_id: int, settings_update: Dict[str, Any]) -> Optional[PushNotificationSettings]:
        """Update user's push notification settings"""
        settings = self._load_settings()
        user_settings = settings.get(str(user_id))
        
        if not user_settings:
            # Create default settings if they don't exist
            return self.create_user_settings(user_id)
        
        # Update settings
        for key, value in settings_update.items():
            if value is not None:
                user_settings[key] = value
        
        user_settings["updated_at"] = datetime.utcnow().isoformat()
        settings[str(user_id)] = user_settings
        self._save_settings(settings)
        
        return PushNotificationSettings(**user_settings)
    
    def count_subscriptions(self) -> int:
        """Count total active subscriptions"""
        subscriptions = self._load_subscriptions()
        return sum(1 for sub in subscriptions.values() if sub.get("is_active", True))
    
    def count_user_subscriptions(self, user_id: int) -> int:
        """Count active subscriptions for a specific user"""
        subscriptions = self._load_subscriptions()
        return sum(1 for sub in subscriptions.values() 
                  if sub.get("user_id") == user_id and sub.get("is_active", True))


# Global instance
push_subscription_storage = PushSubscriptionStorage()
