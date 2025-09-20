#!/usr/bin/env python3
"""
Generate VAPID keys for push notifications
This script generates VAPID keys and saves them to vapid_keys.json
"""

import os
import json
import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.backends import default_backend

def generate_vapid_keys():
    """Generate VAPID keys for push notifications"""
    try:
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
        vapid_public_key = base64.urlsafe_b64encode(public_key_bytes).decode('utf-8').rstrip('=')
        
        # Convert private key to DER format
        private_key_der = private_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        # Convert to URL-safe base64
        vapid_private_key = base64.urlsafe_b64encode(private_key_der).decode('utf-8').rstrip('=')
        
        # Create VAPID keys data
        vapid_data = {
            "public_key": vapid_public_key,
            "private_key": vapid_private_key,
            "email": "admin@shrimpsense.com"
        }
        
        # Save to JSON file
        with open('vapid_keys.json', 'w') as f:
            json.dump(vapid_data, f, indent=2)
        
        print("✅ VAPID keys generated successfully!")
        print(f"Public Key: {vapid_public_key}")
        print(f"Private Key: {vapid_private_key}")
        print("Keys saved to vapid_keys.json")
        
        return vapid_data
        
    except Exception as e:
        print(f"❌ Error generating VAPID keys: {e}")
        raise

if __name__ == "__main__":
    generate_vapid_keys()
