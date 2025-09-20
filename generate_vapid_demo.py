#!/usr/bin/env python3
"""
Generate VAPID keys for demo purposes
"""

from py_vapid import Vapid
import json
import base64
from cryptography.hazmat.primitives import serialization

def generate_vapid_keys():
    """Generate VAPID keys and save to JSON file"""
    try:
        # Generate VAPID keys
        vapid = Vapid()
        vapid.generate_keys()
        
        # Get keys
        public_key = vapid.public_key
        private_key = vapid.private_key
        
        # Convert to base64
        public_key_b64 = base64.urlsafe_b64encode(public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint
        )).decode('utf-8').rstrip('=')
        
        private_key_b64 = base64.urlsafe_b64encode(private_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )).decode('utf-8').rstrip('=')
        
        # Create data
        vapid_data = {
            "public_key": public_key_b64,
            "private_key": private_key_b64,
            "email": "admin@shrimpsense.com"
        }
        
        # Save to JSON file
        with open('vapid_keys.json', 'w') as f:
            json.dump(vapid_data, f, indent=2)
        
        print("✅ VAPID keys generated successfully!")
        print(f"📁 Saved to: vapid_keys.json")
        print(f"🔑 Public Key: {public_key_b64}")
        print(f"🔐 Private Key: {private_key_b64}")
        
        return vapid_data
        
    except Exception as e:
        print(f"❌ Error generating VAPID keys: {e}")
        return None

if __name__ == "__main__":
    generate_vapid_keys()
