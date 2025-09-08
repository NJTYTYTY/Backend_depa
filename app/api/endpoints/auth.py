"""
Authentication endpoints for Backend_PWA
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from typing import Optional

from ...core.config import settings
from ...core.security import (
    create_access_token, 
    create_refresh_token, 
    refresh_access_token,
    verify_token
)
from ...storage import UserStorage
from ...schemas.auth import (
    UserCreate, 
    UserLogin, 
    UserResponse, 
    Token, 
    TokenRefresh,
    UserUpdate
)

router = APIRouter(prefix="/auth", tags=["authentication"])

# Helper functions for dependencies
from fastapi.security import HTTPBearer
security = HTTPBearer()

async def get_token_from_header(credentials = Depends(security)) -> str:
    """
    Extract token from Authorization header
    """
    return credentials.credentials

async def get_current_user_dep(token: str = Depends(get_token_from_header)) -> dict:
    """
    Get current user from token (dependency)
    """
    try:
        payload = verify_token(token, "access")
        user_id = payload.get("sub")
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        
        user = UserStorage.get_by_id(int(user_id))
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

async def get_current_active_user_dep(current_user: dict = Depends(get_current_user_dep)) -> dict:
    """
    Get current active user
    """
    if not current_user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user

async def get_admin_user_dep(current_user: dict = Depends(get_current_active_user_dep)) -> dict:
    """
    Get current admin user
    """
    if not current_user["is_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Admin access required."
        )
    return current_user

@router.post("/register", response_model=UserResponse)
async def register(user: UserCreate):
    """
    Register a new user
    """
    # Check account limit (max 10 users)
    if UserStorage.count() >= 10:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Maximum number of accounts (10) has been reached"
        )
    
    # Check if user already exists by email
    existing_user = UserStorage.get_by_email(user.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if phone number already exists
    existing_user_phone = UserStorage.get_by_phone(user.phone_number)
    if existing_user_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number already registered"
        )
    
    # Create new user (plain text password for demo)
    user_data = {
        "phone_number": user.phone_number,
        "email": user.email,
        "full_name": user.full_name,
        "password": user.password,
        "role": user.role,
        "is_admin": False,
        "is_active": True
    }
    
    created_user = UserStorage.create(user_data)
    
    return UserResponse(
        id=created_user["id"],
        phone_number=created_user["phone_number"],
        email=created_user["email"],
        full_name=created_user["full_name"],
        role=created_user["role"],
        is_admin=created_user["is_admin"],
        is_active=created_user["is_active"],
        created_at=created_user["created_at"]
    )

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Login user and return access token
    """
    # Find user by phone number (form_data.username contains phone number)
    user = UserStorage.get_by_phone(form_data.username)
    
    if not user or form_data.password != user["password"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect phone number or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user["id"])}, expires_delta=access_token_expires
    )
    
    # Create refresh token
    refresh_token = create_refresh_token(data={"sub": str(user["id"])})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_data: TokenRefresh):
    """
    Refresh access token using refresh token
    """
    try:
        # Refresh the access token
        new_access_token = refresh_access_token(refresh_data.refresh_token)
        
        # Get user ID from refresh token
        payload = verify_token(refresh_data.refresh_token, "refresh")
        user_id = payload.get("sub")
        
        # Verify user still exists and is active
        user = UserStorage.get_by_id(int(user_id))
        if not user or not user["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        return {
            "access_token": new_access_token,
            "refresh_token": refresh_data.refresh_token,  # Return same refresh token
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not refresh token"
        )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user_dep)):
    """
    Get current user information
    """
    return UserResponse(
        id=current_user["id"],
        phone_number=current_user["phone_number"],
        email=current_user["email"],
        full_name=current_user["full_name"],
        role=current_user["role"],
        is_admin=current_user["is_admin"],
        is_active=current_user["is_active"],
        created_at=current_user["created_at"]
    )

@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Update current user information
    """
    update_data = {}
    
    # Update allowed fields
    if user_update.full_name is not None:
        update_data["full_name"] = user_update.full_name
    
    if user_update.email is not None:
        # Check if new email is already taken
        existing_user = UserStorage.get_by_email(user_update.email)
        if existing_user and existing_user["id"] != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already taken"
            )
        update_data["email"] = user_update.email
    
    # Update user
    updated_user = UserStorage.update(current_user["id"], update_data)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse(
        id=updated_user["id"],
        phone_number=updated_user["phone_number"],
        email=updated_user["email"],
        full_name=updated_user["full_name"],
        role=updated_user["role"],
        is_admin=updated_user["is_admin"],
        is_active=updated_user["is_active"],
        created_at=updated_user["created_at"]
    )

@router.get("/account-limit")
async def get_account_limit_info():
    """
    Get information about account limit
    """
    user_count = UserStorage.count()
    can_create = user_count < 10
    
    return {
        "current_accounts": user_count,
        "max_accounts": 10,
        "can_create_new": can_create,
        "remaining_slots": max(0, 10 - user_count)
    }

@router.get("/users", response_model=list[UserResponse])
async def get_all_users(current_user: dict = Depends(get_admin_user_dep)):
    """
    Get all users (admin only)
    """
    users = UserStorage.get_all()
    return [
        UserResponse(
            id=user["id"],
            phone_number=user["phone_number"],
            email=user["email"],
            full_name=user["full_name"],
            role=user["role"],
            is_admin=user["is_admin"],
            is_active=user["is_active"],
            created_at=user["created_at"]
        )
        for user in users
    ]

@router.put("/users/{user_id}/admin")
async def toggle_admin_status(
    user_id: int,
    current_user: dict = Depends(get_admin_user_dep)
):
    """
    Toggle admin status for a user (admin only)
    """
    if current_user["id"] == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify your own admin status"
        )
    
    user = UserStorage.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Toggle admin status
    update_data = {"is_admin": not user["is_admin"]}
    updated_user = UserStorage.update(user_id, update_data)
    
    return {
        "message": f"User {user['phone_number']} admin status set to {updated_user['is_admin']}",
        "user": UserResponse(
            id=updated_user["id"],
            phone_number=updated_user["phone_number"],
            email=updated_user["email"],
            full_name=updated_user["full_name"],
            role=updated_user["role"],
            is_admin=updated_user["is_admin"],
            is_active=updated_user["is_active"],
            created_at=updated_user["created_at"]
        )
    }
