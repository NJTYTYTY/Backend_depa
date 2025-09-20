"""
Push Notification Triggers for Shrimp Farm Management System
Handles automatic push notifications based on sensor data and system events
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from ..core.push_service import push_service
from ..storage.push_subscription_storage import push_subscription_storage

logger = logging.getLogger(__name__)

class NotificationTriggers:
    def __init__(self):
        self.last_notifications = {}  # Track last notification time to avoid spam
        
    async def check_sensor_alerts(self, pond_id: str, sensor_data: Dict[str, Any], user_id: int):
        """Check sensor data for alerts and send push notifications"""
        try:
            alerts = []
            
            # Temperature alerts
            if 'temperature' in sensor_data:
                temp = sensor_data['temperature'].get('value', 0)
                if temp > 35:
                    alerts.append({
                        'type': 'temperature_high',
                        'title': '🌡️ อุณหภูมิสูงเกินไป',
                        'body': f'อุณหภูมิในบ่อ {pond_id} สูงถึง {temp}°C',
                        'priority': 'high'
                    })
                elif temp < 20:
                    alerts.append({
                        'type': 'temperature_low',
                        'title': '🌡️ อุณหภูมิต่ำเกินไป',
                        'body': f'อุณหภูมิในบ่อ {pond_id} ต่ำถึง {temp}°C',
                        'priority': 'high'
                    })
            
            # pH alerts
            if 'pH' in sensor_data:
                ph = sensor_data['pH'].get('value', 0)
                if ph > 8.5:
                    alerts.append({
                        'type': 'ph_high',
                        'title': '🧪 pH สูงเกินไป',
                        'body': f'ค่า pH ในบ่อ {pond_id} สูงถึง {ph}',
                        'priority': 'high'
                    })
                elif ph < 6.5:
                    alerts.append({
                        'type': 'ph_low',
                        'title': '🧪 pH ต่ำเกินไป',
                        'body': f'ค่า pH ในบ่อ {pond_id} ต่ำถึง {ph}',
                        'priority': 'high'
                    })
            
            # DO (Dissolved Oxygen) alerts
            if 'DO' in sensor_data:
                do = sensor_data['DO'].get('value', 0)
                if do < 3:
                    alerts.append({
                        'type': 'do_low',
                        'title': '💨 ออกซิเจนละลายน้ำต่ำ',
                        'body': f'ออกซิเจนละลายน้ำในบ่อ {pond_id} ต่ำถึง {do} mg/L',
                        'priority': 'critical'
                    })
            
            # Water color alerts
            if 'waterColor' in sensor_data:
                color = sensor_data['waterColor'].get('value', '')
                if color in ['red', 'brown']:
                    alerts.append({
                        'type': 'water_color_bad',
                        'title': '🌊 สีน้ำผิดปกติ',
                        'body': f'สีน้ำในบ่อ {pond_id} เป็นสี {color}',
                        'priority': 'medium'
                    })
            
            # Send notifications for alerts
            for alert in alerts:
                await self._send_notification(
                    user_id=user_id,
                    title=alert['title'],
                    body=alert['body'],
                    data={
                        'type': alert['type'],
                        'pond_id': pond_id,
                        'priority': alert['priority'],
                        'timestamp': datetime.now().isoformat()
                    },
                    tag=f"sensor_alert_{pond_id}_{alert['type']}"
                )
                
        except Exception as e:
            logger.error(f"Error checking sensor alerts: {e}")
    
    async def check_pond_status_changes(self, pond_id: str, old_status: str, new_status: str, user_id: int):
        """Check for pond status changes and send notifications"""
        try:
            if old_status != new_status:
                status_messages = {
                    'active': '🟢 บ่อกุ้งทำงานปกติ',
                    'maintenance': '🔧 บ่อกุ้งอยู่ในช่วงบำรุงรักษา',
                    'error': '❌ บ่อกุ้งมีปัญหา',
                    'offline': '🔴 บ่อกุ้งออฟไลน์'
                }
                
                title = f"📊 สถานะบ่อกุ้งเปลี่ยนแปลง"
                body = f"บ่อ {pond_id}: {status_messages.get(old_status, old_status)} → {status_messages.get(new_status, new_status)}"
                
                await self._send_notification(
                    user_id=user_id,
                    title=title,
                    body=body,
                    data={
                        'type': 'pond_status_change',
                        'pond_id': pond_id,
                        'old_status': old_status,
                        'new_status': new_status,
                        'timestamp': datetime.now().isoformat()
                    },
                    tag=f"pond_status_{pond_id}"
                )
                
        except Exception as e:
            logger.error(f"Error checking pond status changes: {e}")
    
    async def check_system_updates(self, update_type: str, message: str, user_id: int):
        """Send system update notifications"""
        try:
            update_messages = {
                'maintenance': '🔧 ระบบบำรุงรักษา',
                'update': '🔄 อัปเดตระบบ',
                'security': '🔒 การรักษาความปลอดภัย',
                'feature': '✨ ฟีเจอร์ใหม่'
            }
            
            title = f"🔔 {update_messages.get(update_type, 'การแจ้งเตือนระบบ')}"
            body = message
            
            await self._send_notification(
                user_id=user_id,
                title=title,
                body=body,
                data={
                    'type': 'system_update',
                    'update_type': update_type,
                    'timestamp': datetime.now().isoformat()
                },
                tag=f"system_{update_type}"
            )
            
        except Exception as e:
            logger.error(f"Error sending system update notification: {e}")
    
    async def check_maintenance_alerts(self, pond_id: str, maintenance_type: str, user_id: int):
        """Send maintenance alerts"""
        try:
            maintenance_messages = {
                'filter_clean': '🧽 ควรทำความสะอาดตัวกรอง',
                'sensor_calibrate': '🔧 ควรปรับเทียบเซ็นเซอร์',
                'water_change': '💧 ควรเปลี่ยนน้ำ',
                'feeding_schedule': '🍽️ ถึงเวลาป้อนอาหาร',
                'health_check': '🏥 ควรตรวจสุขภาพกุ้ง'
            }
            
            title = f"⏰ แจ้งเตือนการบำรุงรักษา"
            body = f"บ่อ {pond_id}: {maintenance_messages.get(maintenance_type, maintenance_type)}"
            
            await self._send_notification(
                user_id=user_id,
                title=title,
                body=body,
                data={
                    'type': 'maintenance_alert',
                    'pond_id': pond_id,
                    'maintenance_type': maintenance_type,
                    'timestamp': datetime.now().isoformat()
                },
                tag=f"maintenance_{pond_id}_{maintenance_type}"
            )
            
        except Exception as e:
            logger.error(f"Error sending maintenance alert: {e}")
    
    async def _send_notification(self, user_id: int, title: str, body: str, data: Dict[str, Any], tag: str):
        """Send push notification to user"""
        try:
            # Check if we've sent this notification recently (avoid spam)
            notification_key = f"{user_id}_{tag}"
            now = datetime.now()
            
            if notification_key in self.last_notifications:
                last_sent = self.last_notifications[notification_key]
                # Don't send same notification within 5 minutes
                if (now - last_sent).total_seconds() < 300:
                    return
            
            # Create push message
            from ..schemas.push_notification import PushMessage
            
            message = PushMessage(
                title=title,
                body=body,
                icon="/icons/icon-192x192.png",
                badge="/icons/icon-72x72.png",
                data=data,
                tag=tag,
                require_interaction=True,
                vibrate=[200, 100, 200]
            )
            
            # Send notification
            response = push_service.send_push_to_user(user_id, message)
            
            if response.success:
                self.last_notifications[notification_key] = now
                logger.info(f"Push notification sent to user {user_id}: {title}")
            else:
                logger.error(f"Failed to send push notification to user {user_id}: {response.message}")
                
        except Exception as e:
            logger.error(f"Error sending push notification: {e}")

# Global instance
notification_triggers = NotificationTriggers()
