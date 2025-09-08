"""
Authentication schemas for Backend_PWA
"""

from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime
import re

class UserBase(BaseModel):
    """Base user schema"""
    phone_number: str = Field(..., description="Phone number (e.g., 0812345678)")
    email: EmailStr
    full_name: Optional[str] = Field(None, max_length=255)
    role: str = Field(default="viewer", pattern="^(admin|owner|operator|viewer)$")
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        # Remove spaces, dashes, and parentheses
        clean_phone = re.sub(r'[\s\-\(\)]', '', v)
        # Check if it's a valid Thai phone number
        if not re.match(r'^0[689]\d{8}$', clean_phone):
            raise ValueError('Invalid Thai phone number format. Use format: 0812345678')
        return clean_phone

class UserCreate(UserBase):
    """Schema for creating a new user"""
    password: str = Field(..., min_length=6, max_length=100)

class UserLogin(BaseModel):
    """Schema for user login"""
    phone_number: str = Field(..., description="Phone number for login")
    password: str
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        # Remove spaces, dashes, and parentheses
        clean_phone = re.sub(r'[\s\-\(\)]', '', v)
        # Check if it's a valid Thai phone number
        if not re.match(r'^0[689]\d{8}$', clean_phone):
            raise ValueError('Invalid Thai phone number format. Use format: 0812345678')
        return clean_phone

class UserUpdate(BaseModel):
    """Schema for updating user information"""
    phone_number: Optional[str] = Field(None, description="Phone number")
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=255)
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        if v is None:
            return v
        # Remove spaces, dashes, and parentheses
        clean_phone = re.sub(r'[\s\-\(\)]', '', v)
        # Check if it's a valid Thai phone number
        if not re.match(r'^0[689]\d{8}$', clean_phone):
            raise ValueError('Invalid Thai phone number format. Use format: 0812345678')
        return clean_phone

class UserResponse(UserBase):
    """Schema for user response"""
    id: int
    is_active: bool
    is_admin: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class Token(BaseModel):
    """Schema for authentication token"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class TokenRefresh(BaseModel):
    """Schema for token refresh request"""
    refresh_token: str

class TokenData(BaseModel):
    """Schema for token data"""
    user_id: Optional[int] = None
    token_type: Optional[str] = None

class PasswordChange(BaseModel):
    """Schema for password change"""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)

class UserStatusUpdate(BaseModel):
    """Schema for updating user status"""
    is_active: bool

class UserRoleUpdate(BaseModel):
    """Schema for updating user role"""
    role: str = Field(..., pattern="^(owner|operator|viewer)$")
