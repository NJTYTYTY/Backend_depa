"""
Alert Storage System for Shrimp Farm Alert System
Handles storage and retrieval of alert data
"""

import os
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from ..schemas.alert import AlertData, AlertStatus, AlertType, AlertSeverity, parse_alert_type, create_alert_id

# File paths
ALERTS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend", "data", "alerts.json")

class AlertStorage:
    """Storage class for managing alert data"""
    
    @staticmethod
    def _read_alerts() -> List[Dict[str, Any]]:
        """Read alerts from JSON file"""
        try:
            if os.path.exists(ALERTS_FILE):
                with open(ALERTS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            print(f"Error reading alerts file: {e}")
            return []
    
    @staticmethod
    def _write_alerts(alerts: List[Dict[str, Any]]) -> bool:
        """Write alerts to JSON file"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(ALERTS_FILE), exist_ok=True)
            
            with open(ALERTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(alerts, f, indent=2, ensure_ascii=False, default=str)
            return True
        except Exception as e:
            print(f"Error writing alerts file: {e}")
            return False
    
    @staticmethod
    def _generate_id() -> str:
        """Generate unique alert ID"""
        import time
        return f"alert_{int(time.time() * 1000)}_{hash(str(time.time())) % 10000}"
    
    @staticmethod
    def create_alert(alert_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new alert"""
        try:
            alerts = AlertStorage._read_alerts()
            
            # Generate unique ID
            alert_id = create_alert_id(
                alert_data.get('alert_type', ''),
                alert_data.get('pond_id', 0),
                alert_data.get('user_id', 0)
            )
            
            # Create alert object
            new_alert = {
                "id": alert_id,
                "alert_type": alert_data.get('alert_type', ''),
                "pond_id": alert_data.get('pond_id', 0),
                "user_id": alert_data.get('user_id', 0),
                "title": alert_data.get('title', ''),
                "body": alert_data.get('body', ''),
                "status": alert_data.get('status', 'unread'),
                "severity": alert_data.get('severity', 'medium'),
                "image_url": alert_data.get('image_url'),
                "target_url": alert_data.get('target_url'),
                "data": alert_data.get('data', {}),
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": None,
                "read_at": None
            }
            
            alerts.append(new_alert)
            
            if AlertStorage._write_alerts(alerts):
                return new_alert
            return None
            
        except Exception as e:
            print(f"Error creating alert: {e}")
            return None
    
    @staticmethod
    def get_alert_by_id(alert_id: str) -> Optional[Dict[str, Any]]:
        """Get alert by ID"""
        try:
            alerts = AlertStorage._read_alerts()
            return next((alert for alert in alerts if alert.get('id') == alert_id), None)
        except Exception as e:
            print(f"Error getting alert by ID: {e}")
            return None
    
    @staticmethod
    def get_alerts_by_user(user_id: int) -> List[Dict[str, Any]]:
        """Get all alerts for a specific user"""
        try:
            alerts = AlertStorage._read_alerts()
            return [alert for alert in alerts if alert.get('user_id') == user_id]
        except Exception as e:
            print(f"Error getting alerts by user: {e}")
            return []
    
    @staticmethod
    def get_alerts_by_pond(pond_id: int) -> List[Dict[str, Any]]:
        """Get all alerts for a specific pond"""
        try:
            alerts = AlertStorage._read_alerts()
            return [alert for alert in alerts 
                   if (alert.get('pond_id') == pond_id or 
                       alert.get('pond_id') == str(pond_id))]
        except Exception as e:
            print(f"Error getting alerts by pond: {e}")
            return []
    
    @staticmethod
    def get_alerts_by_user_and_pond(user_id: int, pond_id: int) -> List[Dict[str, Any]]:
        """Get alerts for specific user and pond"""
        try:
            alerts = AlertStorage._read_alerts()
            return [alert for alert in alerts 
                   if alert.get('user_id') == user_id and 
                   (alert.get('pond_id') == pond_id or 
                    alert.get('pond_id') == str(pond_id))]
        except Exception as e:
            print(f"Error getting alerts by user and pond: {e}")
            return []
    
    @staticmethod
    def get_unread_alerts_by_user(user_id: int) -> List[Dict[str, Any]]:
        """Get unread alerts for a specific user"""
        try:
            alerts = AlertStorage._read_alerts()
            return [alert for alert in alerts 
                   if alert.get('user_id') == user_id and alert.get('status') == 'unread']
        except Exception as e:
            print(f"Error getting unread alerts by user: {e}")
            return []
    
    @staticmethod
    def get_unread_alerts_by_pond(pond_id: int) -> List[Dict[str, Any]]:
        """Get unread alerts for a specific pond"""
        try:
            alerts = AlertStorage._read_alerts()
            return [alert for alert in alerts 
                   if (alert.get('pond_id') == pond_id or 
                       alert.get('pond_id') == str(pond_id)) and 
                   alert.get('status') == 'unread']
        except Exception as e:
            print(f"Error getting unread alerts by pond: {e}")
            return []
    
    @staticmethod
    def update_alert_status(alert_id: str, status: str, read_at: Optional[datetime] = None) -> bool:
        """Update alert status"""
        try:
            alerts = AlertStorage._read_alerts()
            
            for alert in alerts:
                if alert.get('id') == alert_id:
                    alert['status'] = status
                    alert['updated_at'] = datetime.utcnow().isoformat()
                    if read_at:
                        alert['read_at'] = read_at.isoformat()
                    break
            
            return AlertStorage._write_alerts(alerts)
            
        except Exception as e:
            print(f"Error updating alert status: {e}")
            return False
    
    @staticmethod
    def mark_alert_as_read(alert_id: str) -> bool:
        """Mark alert as read"""
        return AlertStorage.update_alert_status(alert_id, 'read', datetime.utcnow())
    
    @staticmethod
    def mark_alert_as_unread(alert_id: str) -> bool:
        """Mark alert as unread"""
        return AlertStorage.update_alert_status(alert_id, 'unread')
    
    @staticmethod
    def delete_alert(alert_id: str) -> bool:
        """Delete an alert"""
        try:
            alerts = AlertStorage._read_alerts()
            alerts = [alert for alert in alerts if alert.get('id') != alert_id]
            return AlertStorage._write_alerts(alerts)
        except Exception as e:
            print(f"Error deleting alert: {e}")
            return False
    
    @staticmethod
    def get_alert_stats_by_user(user_id: int) -> Dict[str, Any]:
        """Get alert statistics for a user"""
        try:
            alerts = AlertStorage.get_alerts_by_user(user_id)
            
            stats = {
                "total_alerts": len(alerts),
                "unread_alerts": len([a for a in alerts if a.get('status') == 'unread']),
                "alerts_by_type": {},
                "alerts_by_pond": {},
                "alerts_by_severity": {}
            }
            
            # Count by type
            for alert in alerts:
                alert_type = alert.get('alert_type', '')
                base_type, _ = parse_alert_type(alert_type)
                stats["alerts_by_type"][base_type] = stats["alerts_by_type"].get(base_type, 0) + 1
            
            # Count by pond
            for alert in alerts:
                pond_id = alert.get('pond_id', 0)
                stats["alerts_by_pond"][pond_id] = stats["alerts_by_pond"].get(pond_id, 0) + 1
            
            # Count by severity
            for alert in alerts:
                severity = alert.get('severity', 'medium')
                stats["alerts_by_severity"][severity] = stats["alerts_by_severity"].get(severity, 0) + 1
            
            return stats
            
        except Exception as e:
            print(f"Error getting alert stats: {e}")
            return {
                "total_alerts": 0,
                "unread_alerts": 0,
                "alerts_by_type": {},
                "alerts_by_pond": {},
                "alerts_by_severity": {}
            }
    
    @staticmethod
    def check_pond_has_unread_alerts(pond_id: int) -> bool:
        """Check if pond has any unread alerts"""
        try:
            unread_alerts = AlertStorage.get_unread_alerts_by_pond(pond_id)
            return len(unread_alerts) > 0
        except Exception as e:
            print(f"Error checking pond unread alerts: {e}")
            return False
    
    @staticmethod
    def get_pond_alert_badge_count(pond_id: int) -> int:
        """Get count of unread alerts for pond badge"""
        try:
            unread_alerts = AlertStorage.get_unread_alerts_by_pond(pond_id)
            return len(unread_alerts)
        except Exception as e:
            print(f"Error getting pond alert badge count: {e}")
            return 0
