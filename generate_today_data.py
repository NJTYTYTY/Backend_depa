#!/usr/bin/env python3
"""
Generate additional fake data for today (September 29, 2025)
"""

import json
import random
from datetime import datetime, timedelta

def generate_today_data():
    # Load existing data
    with open('data/graph_data.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Generate data for today (September 29, 2025)
    today = datetime(2025, 9, 29)
    
    # Generate 24 hours of data for today
    for hour in range(24):
        timestamp = today.replace(hour=hour, minute=0, second=0, microsecond=0)
        
        # Generate realistic sensor values with some variation
        do_value = round(random.uniform(4.5, 8.0), 1)
        ph_value = round(random.uniform(6.5, 8.5), 1)
        temp_value = round(random.uniform(28.0, 32.0), 1)
        
        # Determine status based on values
        do_status = "green" if do_value >= 5.0 else "yellow" if do_value >= 3.0 else "red"
        ph_status = "green" if 6.5 <= ph_value <= 8.5 else "yellow" if 6.0 <= ph_value <= 9.0 else "red"
        temp_status = "green" if 28.0 <= temp_value <= 32.0 else "yellow" if 27.0 <= temp_value <= 33.0 else "red"
        
        # Create batch data
        batch = {
            "timestamp": timestamp.isoformat() + "+00:00",
            "sensors": {
                "DO": {
                    "value": do_value,
                    "type": "numeric",
                    "status": do_status
                },
                "pH": {
                    "value": ph_value,
                    "type": "numeric",
                    "status": ph_status
                },
                "temperature": {
                    "value": temp_value,
                    "type": "numeric",
                    "status": temp_status
                }
            }
        }
        
        data.append(batch)
    
    # Save updated data
    with open('data/graph_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Generated data for {today.strftime('%Y-%m-%d')} (24 hours)")
    print(f"Total batches: {len(data)}")

if __name__ == "__main__":
    generate_today_data()
