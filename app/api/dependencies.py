"""
FastAPI dependencies for Backend_PWA
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from typing import Optional

from ..core.security import verify_token
from ..storage import UserStorage

# Security scheme
security = HTTPBearer()

async def get_current_user(token: str = Depends(security)) -> dict:
    """
    Get current user from JWT token
    """
    try:
        # ใช้ token.credentials สำหรับ HTTPBearer
        payload = verify_token(token.credentials, "access")
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
        print(f"❌ Token validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

async def get_current_active_user(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Get current active user
    """
    if not current_user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user

async def get_admin_user(current_user: dict = Depends(get_current_active_user)) -> dict:
    """
    Get current admin user
    """
    if not current_user["is_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Admin access required."
        )
    return current_user

async def get_owner_or_admin_user(current_user: dict = Depends(get_current_active_user)) -> dict:
    """
    Get current user who is either owner or admin
    """
    if current_user["is_admin"]:
        return current_user
    
    # Check if user has owner role
    if current_user["role"] == "owner":
        return current_user
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not enough permissions. Owner or admin access required."
    )

async def check_account_limit_dependency() -> bool:
    """
    Check if account limit allows creating new users
    """
    user_count = UserStorage.count()
    return user_count < 10

def verify_pond_ownership(pond_id: int, current_user: dict) -> dict:
    """
    Verify pond ownership and return pond object
    """
    from ..storage import PondStorage
    
    pond = PondStorage.get_by_id(pond_id)
    if not pond:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Pond not found"
        )
    
    # Admin can access all ponds, owners can access their own ponds
    if not current_user["is_admin"] and pond["owner_id"] != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Not authorized to access this pond"
        )
    
    return pond

# Legacy functions for compatibility
async def get_db_session():
    """
    Legacy function for compatibility - no longer needed with JSON storage
    """
    return None

async def get_db():
    """
    Legacy function for compatibility - no longer needed with JSON storage
    """
    return None