#!/usr/bin/env python3
"""
Generate fake sensor data for testing
"""

import json
from datetime import datetime, timedelta
import random

def generate_fake_data():
    # Load existing data
    with open('backend/data/graph_data.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"Current data points: {len(data)}")
    
    # Generate 10 days of additional data (240 hours)
    base_date = datetime(2025, 9, 18)  # Start 10 days before current data
    
    for day in range(10):
        for hour in range(24):
            timestamp = base_date + timedelta(days=day, hours=hour)
            
            # Generate realistic sensor data with some variation
            do_value = round(random.uniform(2.0, 8.0), 1)
            ph_value = round(random.uniform(6.0, 8.5), 1)
            temp_value = round(random.uniform(22.0, 30.0), 1)
            
            # Determine status based on values
            do_status = 'green' if do_value >= 5.0 else ('yellow' if do_value >= 3.0 else 'red')
            ph_status = 'green' if 6.5 <= ph_value <= 8.0 else ('yellow' if 6.0 <= ph_value <= 8.5 else 'red')
            temp_status = 'green' if 25.0 <= temp_value <= 32.0 else ('yellow' if 22.0 <= temp_value <= 35.0 else 'red')
            
            entry = {
                'id': f'graph_demo_{day:02d}_{hour:02d}',
                'pond_id': 1,
                'timestamp': timestamp.isoformat() + '+00:00',
                'sensors': {
                    'DO': {
                        'value': do_value,
                        'type': 'numeric',
                        'status': do_status
                    },
                    'pH': {
                        'value': ph_value,
                        'type': 'numeric',
                        'status': ph_status
                    },
                    'temperature': {
                        'value': temp_value,
                        'type': 'numeric',
                        'status': temp_status
                    }
                }
            }
            
            data.append(entry)
    
    # Save updated data
    with open('backend/data/graph_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f'Generated {10 * 24} additional data points')
    print(f'Total data points: {len(data)}')
    print('Data saved to data/graph_data.json')

if __name__ == "__main__":
    generate_fake_data()
