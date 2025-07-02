from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from database import get_database
from models.user import User
from schemas.user import UserResponse, UserUpdate
from dependencies import get_current_user

router = APIRouter()

@router.get("/profile", response_model=UserResponse)
async def get_profile(current_user: User = Depends(get_current_user)):
    """Get user profile"""
    return current_user

@router.put("/profile", response_model=UserResponse)
async def update_profile(
    update_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database)
):
    """Update user profile"""
    # Only allow non-admin users to update their name
    if update_data.first_name is not None:
        current_user.first_name = update_data.first_name
    if update_data.last_name is not None:
        current_user.last_name = update_data.last_name
    
    # Prevent non-admin users from changing admin-only fields
    if not current_user.is_admin:
        if any([update_data.balance, update_data.is_fake, update_data.is_active]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required for these fields"
            )
    
    await db.commit()
    await db.refresh(current_user)
    return current_user

@router.get("/balance")
async def get_balance(current_user: User = Depends(get_current_user)):
    """Get user balance"""
    return {"balance": current_user.balance}

