#!/usr/bin/env python3
"""
Generate fake shrimp size data for testing
"""

import json
from datetime import datetime, timedelta
import random

def generate_fake_shrimp_data():
    # Load existing data
    with open('backend/data/graph_shrimpsize.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"Current shrimp size data points: {len(data)}")
    
    # Generate 10 days of additional data (240 hours)
    base_date = datetime(2025, 9, 18)  # Start 10 days before current data
    
    for day in range(10):
        for hour in range(24):
            timestamp = base_date + timedelta(days=day, hours=hour)
            
            # Generate realistic shrimp size data with gradual growth
            # Start from 1.5cm and grow to 2.5cm over 10 days
            base_size = 1.5 + (day * 0.1) + (hour * 0.004)  # Gradual growth
            shrimp_size = round(base_size + random.uniform(-0.1, 0.1), 1)
            
            entry = {
                'id': f'shrimp_size_demo_{day:02d}_{hour:02d}',
                'pond_id': 1,
                'timestamp': timestamp.isoformat() + '+00:00',
                'shrimp_size': shrimp_size
            }
            
            data.append(entry)
    
    # Save updated data
    with open('backend/data/graph_shrimpsize.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f'Generated {10 * 24} additional shrimp size data points')
    print(f'Total shrimp size data points: {len(data)}')
    print('Data saved to backend/data/graph_shrimpsize.json')

if __name__ == "__main__":
    generate_fake_shrimp_data()
