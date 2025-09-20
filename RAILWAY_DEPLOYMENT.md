# Railway Deployment Guide

## การแก้ไขปัญหา VAPID Keys

### ปัญหาที่พบ
```
ERROR:app.core.push_service:Failed to generate VAPID keys: curve must be an EllipticCurve instance
```

### วิธีแก้ไข

1. **อัปเดต requirements.txt**
   - เพิ่ม `cryptography>=41.0.0,<43.0.0` เพื่อใช้ version ที่เข้ากันได้

2. **แก้ไข push_service.py**
   - เปลี่ยนจาก `py_vapid` library เป็นใช้ `cryptography` โดยตรง
   - ใช้ `ec.generate_private_key()` แทน `Vapid().generate_keys()`

3. **สร้าง VAPID keys ล่วงหน้า**
   - ใช้ `generate_vapid_keys.py` เพื่อสร้าง keys ก่อน deploy
   - ไฟล์ `vapid_keys.json` จะถูกสร้างอัตโนมัติ

### ไฟล์ที่แก้ไข

1. **backend/app/core/push_service.py**
   - แก้ไข `_generate_vapid_keys()` method
   - ใช้ cryptography library โดยตรง

2. **backend/requirements.txt**
   - เพิ่ม cryptography version constraint

3. **backend/generate_vapid_keys.py**
   - สคริปต์สร้าง VAPID keys

4. **backend/startup.py**
   - เพิ่มการตรวจสอบ VAPID keys ก่อนเริ่ม server

### การ Deploy

1. **Push ไปยัง Git repository**
   ```bash
   git add .
   git commit -m "Fix VAPID keys generation for Railway deployment"
   git push
   ```

2. **Railway จะทำการ deploy อัตโนมัติ**
   - VAPID keys จะถูกสร้างอัตโนมัติใน startup script
   - Server จะเริ่มทำงานได้ปกติ

### การทดสอบ

1. **ตรวจสอบ Health Endpoint**
   ```bash
   curl https://your-railway-app.railway.app/health
   ```

2. **ตรวจสอบ VAPID Keys**
   ```bash
   curl https://your-railway-app.railway.app/api/v1/push/vapid-keys
   ```

### Environment Variables

ไม่จำเป็นต้องตั้งค่า environment variables เพิ่มเติม VAPID keys จะถูกสร้างอัตโนมัติ

### หมายเหตุ

- VAPID keys จะถูกสร้างใหม่ทุกครั้งที่ deploy
- Keys จะถูกบันทึกใน `vapid_keys.json` (ไม่ถูก commit)
- หากต้องการใช้ keys เดิม ให้ copy จาก production server
