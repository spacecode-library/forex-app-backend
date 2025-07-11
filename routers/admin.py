# from fastapi import APIRouter, Depends, HTTPException, Query, status
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select, func, and_
# from typing import List
# from uuid import UUID

# from database import get_database
# from models.user import User
# from models.trade import Trade, TradeStatus
# from schemas.user import UserCreate, UserResponse, UserUpdate
# from auth.jwt_handler import get_password_hash
# from dependencies import get_admin_user

# router = APIRouter()

# @router.post("/users", response_model=UserResponse)
# async def create_user(
#     user_data: UserCreate,
#     admin_user: User = Depends(get_admin_user),
#     db: AsyncSession = Depends(get_database)
# ):
#     """Create a new user (admin only)"""
#     # Check if username already exists
#     result = await db.execute(select(User).where(User.username == user_data.username))
#     if result.scalar_one_or_none():
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Username already exists"
#         )
    
#     # Create new user
#     hashed_password = get_password_hash(user_data.password)
#     new_user = User(
#         first_name=user_data.first_name,
#         last_name=user_data.last_name,
#         username=user_data.username,
#         hashed_password=hashed_password,
#         is_admin=user_data.is_admin,
#         balance=user_data.balance,
#         is_fake=user_data.is_fake
#     )
    
#     db.add(new_user)
#     await db.commit()
#     await db.refresh(new_user)
    
#     return new_user

# @router.get("/users", response_model=List[UserResponse])
# async def list_users(
#     admin_user: User = Depends(get_admin_user),
#     db: AsyncSession = Depends(get_database),
#     limit: int = Query(50, le=100),
#     offset: int = Query(0, ge=0),
#     active_only: bool = Query(True)
# ):
#     """List all users (admin only)"""
#     query = select(User).where(User.is_deleted == False)
    
#     if active_only:
#         query = query.where(User.is_active == True)
    
#     query = query.limit(limit).offset(offset)
#     result = await db.execute(query)
#     users = result.scalars().all()
    
#     return users

# @router.put("/users/{user_id}", response_model=UserResponse)
# async def update_user(
#     user_id: UUID,
#     update_data: UserUpdate,
#     admin_user: User = Depends(get_admin_user),
#     db: AsyncSession = Depends(get_database)
# ):
#     """Update user settings (admin only)"""
#     result = await db.execute(select(User).where(User.id == user_id))
#     user = result.scalar_one_or_none()
    
#     if not user:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="User not found"
#         )
    
#     # Update fields
#     if update_data.first_name is not None:
#         user.first_name = update_data.first_name
#     if update_data.last_name is not None:
#         user.last_name = update_data.last_name
#     if update_data.balance is not None:
#         user.balance = update_data.balance
#     if update_data.is_fake is not None:
#         # Check if user has open positions before changing fake mode
#         open_trades = await db.execute(
#             select(Trade).where(
#                 and_(
#                     Trade.users_id == user_id,
#                     Trade.status == TradeStatus.EXECUTED
#                 )
#             )
#         )
#         if open_trades.scalars().first():
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="Cannot change fake mode with open positions"
#             )
#         user.is_fake = update_data.is_fake
#     if update_data.is_active is not None:
#         user.is_active = update_data.is_active
    
#     await db.commit()
#     await db.refresh(user)
    
#     return user

# @router.delete("/users/{user_id}")
# async def delete_user(
#     user_id: UUID,
#     admin_user: User = Depends(get_admin_user),
#     db: AsyncSession = Depends(get_database)
# ):
#     """Soft delete user (admin only)"""
#     result = await db.execute(select(User).where(User.id == user_id))
#     user = result.scalar_one_or_none()
    
#     if not user:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="User not found"
#         )
    
#     user.is_deleted = True
#     user.is_active = False
    
#     await db.commit()
    
#     return {"message": "User deleted successfully"}

# @router.get("/dashboard")
# async def get_admin_dashboard(
#     admin_user: User = Depends(get_admin_user),
#     db: AsyncSession = Depends(get_database)
# ):
#     """Get admin dashboard statistics"""
#     # User statistics
#     total_users = await db.execute(select(func.count(User.id)).where(User.is_deleted == False))
#     active_users = await db.execute(select(func.count(User.id)).where(and_(User.is_active == True, User.is_deleted == False)))
#     fake_users = await db.execute(select(func.count(User.id)).where(and_(User.is_fake == True, User.is_deleted == False)))
    
#     # Trade statistics
#     total_trades = await db.execute(select(func.count(Trade.id)))
#     real_trades = await db.execute(select(func.count(Trade.id)).where(Trade.is_fake == False))
#     fake_trades = await db.execute(select(func.count(Trade.id)).where(Trade.is_fake == True))
    
#     # P/L statistics
#     total_profit = await db.execute(select(func.sum(Trade.profit)).where(Trade.status == TradeStatus.CLOSED))
#     real_profit = await db.execute(select(func.sum(Trade.profit)).where(and_(Trade.status == TradeStatus.CLOSED, Trade.is_fake == False)))
    
#     return {
#         "users": {
#             "total": total_users.scalar() or 0,
#             "active": active_users.scalar() or 0,
#             "fake_mode": fake_users.scalar() or 0
#         },
#         "trades": {
#             "total": total_trades.scalar() or 0,
#             "real": real_trades.scalar() or 0,
#             "fake": fake_trades.scalar() or 0
#         },
#         "profit": {
#             "total": total_profit.scalar() or 0.0,
#             "real_only": real_profit.scalar() or 0.0
#         }
#     }

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import List, Optional
from uuid import UUID
import secrets
from datetime import datetime
from pydantic import BaseModel, Field , field_validator
from pydantic import UUID4
from typing import Optional


from database import get_database
from models.user import User
from models.trade import Trade, TradeStatus
from schemas.user import UserCreate, UserResponse, UserUpdate
from auth.jwt_handler import get_password_hash
from dependencies import get_admin_user
from config import settings

router = APIRouter()

import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ===== INITIAL ADMIN CREATION =====

@router.post("/setup/create-admin", response_model=UserResponse)
async def create_initial_admin(
    user_data: UserCreate,
    setup_key: str,
    db: AsyncSession = Depends(get_database)
):
    """
    Create the initial admin user for system setup.
    This endpoint can only be used when no admin users exist.
    Requires a setup key for security.
    """
    # Check setup key (you should set this in your environment variables)
    expected_setup_key = getattr(settings, 'ADMIN_SETUP_KEY', 'setup_admin_2024')
    if setup_key != expected_setup_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid setup key"
        )
    
    # Check if any admin users already exist
    admin_exists = await db.execute(
        select(func.count(User.id)).where(
            and_(User.is_admin == True, User.is_deleted == False)
        )
    )
    
    if admin_exists.scalar() > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin user already exists. Use regular admin endpoints to create additional users."
        )
    
    # Check if username already exists
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    
    # Force admin privileges for this endpoint
    hashed_password = get_password_hash(user_data.password)
    admin_user = User(
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        username=user_data.username,
        hashed_password=hashed_password,
        is_admin=True,  # Force admin
        balance=user_data.balance or 50000.0,  # Give admin a higher balance
        is_fake=False,  # Admins typically use live accounts
        is_active=True
    )
    
    db.add(admin_user)
    await db.commit()
    await db.refresh(admin_user)
    
    return admin_user

@router.post("/create-admin", response_model=UserResponse)
async def create_additional_admin(
    user_data: UserCreate,
    current_admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_database)
):
    """
    Create additional admin users (admin only).
    Only existing admins can create new admin users.
    """
    # Check if username already exists
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    
    # Create new admin user
    hashed_password = get_password_hash(user_data.password)
    new_admin = User(
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        username=user_data.username,
        hashed_password=hashed_password,
        is_admin=True,  # Force admin privileges
        balance=user_data.balance or 50000.0,
        is_fake=user_data.is_fake or False,
        is_active=True
    )
    
    db.add(new_admin)
    await db.commit()
    await db.refresh(new_admin)
    
    return new_admin

# ===== USER PROFILE MANAGEMENT =====

# @router.post("/users", response_model=UserResponse)
# async def create_user_profile(
#     user_data: UserCreate,
#     admin_user: User = Depends(get_admin_user),
#     db: AsyncSession = Depends(get_database)
# ):
#     """
#     Create a new user profile (admin only).
#     This creates login credentials for users.
#     """
#     # Check if username already exists
#     result = await db.execute(select(User).where(User.username == user_data.username))
#     if result.scalar_one_or_none():
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Username already exists"
#         )
    
#     # Validate input data
#     if len(user_data.username) < 3:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Username must be at least 3 characters long"
#         )
    
#     if len(user_data.password) < 6:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Password must be at least 6 characters long"
#         )
    
#     # Create new user with hashed password
#     hashed_password = get_password_hash(user_data.password)
#     new_user = User(
#         first_name=user_data.first_name,
#         last_name=user_data.last_name,
#         username=user_data.username,
#         hashed_password=hashed_password,
#         is_admin=user_data.is_admin or False,  # Default to regular user
#         balance=user_data.balance or 10000.0,  # Default balance
#         is_fake=user_data.is_fake if user_data.is_fake is not None else True,  # Default to demo
#         is_active=True
#     )
    
#     db.add(new_user)
#     await db.commit()
#     await db.refresh(new_user)
    
#     return new_user


@router.post("/users", response_model=UserResponse)
async def create_user_profile(
    user_data: UserCreate,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_database)
):
    """
    Create a new user profile with leverage setting (admin only).
    """
    # Check if username already exists
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    
    # Validate input data
    if len(user_data.username) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must be at least 3 characters long"
        )
    
    if len(user_data.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long"
        )
    
    # Create new user with hashed password and leverage
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        username=user_data.username,
        hashed_password=hashed_password,
        is_admin=user_data.is_admin or False,
        balance=user_data.balance or 10000.0,
        leverage=user_data.leverage or settings.DEFAULT_LEVERAGE,  # NEW: Set leverage
        is_fake=user_data.is_fake if user_data.is_fake is not None else True,
        is_active=True
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    logger.info(f"Admin {admin_user.username} created new user {new_user.username} with leverage {new_user.leverage}:1")
    
    return new_user

@router.post("/users/bulk", response_model=List[UserResponse])
async def create_bulk_users(
    users_data: List[UserCreate],
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_database)
):
    """
    Create multiple user profiles at once (admin only).
    Useful for batch user creation.
    """
    if len(users_data) > 50:  # Limit bulk creation
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create more than 50 users at once"
        )
    
    created_users = []
    failed_users = []
    
    for user_data in users_data:
        try:
            # Check if username already exists
            result = await db.execute(select(User).where(User.username == user_data.username))
            if result.scalar_one_or_none():
                failed_users.append({
                    "username": user_data.username,
                    "error": "Username already exists"
                })
                continue
            
            # Create user
            hashed_password = get_password_hash(user_data.password)
            new_user = User(
                first_name=user_data.first_name,
                last_name=user_data.last_name,
                username=user_data.username,
                hashed_password=hashed_password,
                is_admin=user_data.is_admin or False,
                balance=user_data.balance or 10000.0,
                is_fake=user_data.is_fake if user_data.is_fake is not None else True,
                is_active=True
            )
            
            db.add(new_user)
            created_users.append(new_user)
            
        except Exception as e:
            failed_users.append({
                "username": user_data.username,
                "error": str(e)
            })
    
    await db.commit()
    
    # Refresh all created users
    for user in created_users:
        await db.refresh(user)
    
    if failed_users:
        # Return partial success with error details
        return {
            "created_users": created_users,
            "failed_users": failed_users,
            "message": f"Created {len(created_users)} users, {len(failed_users)} failed"
        }
    
    return created_users

@router.get("/users", response_model=List[UserResponse])
async def list_user_profiles(
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_database),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    active_only: bool = Query(True),
    search: Optional[str] = Query(None),
    is_admin: Optional[bool] = Query(None),
    is_fake: Optional[bool] = Query(None)
):
    """
    List all user profiles with filtering options (admin only).
    """
    query = select(User).where(User.is_deleted == False)
    
    # Apply filters
    if active_only:
        query = query.where(User.is_active == True)
    
    if search:
        search_term = f"%{search}%"
        query = query.where(
            (User.first_name.ilike(search_term)) |
            (User.last_name.ilike(search_term)) |
            (User.username.ilike(search_term))
        )
    
    if is_admin is not None:
        query = query.where(User.is_admin == is_admin)
    
    if is_fake is not None:
        query = query.where(User.is_fake == is_fake)
    
    # Apply pagination
    query = query.limit(limit).offset(offset)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return users

# @router.put("/users/{user_id}", response_model=UserResponse)
# async def update_user_profile(
#     user_id: UUID,
#     update_data: UserUpdate,
#     admin_user: User = Depends(get_admin_user),
#     db: AsyncSession = Depends(get_database)
# ):
#     """
#     Update user profile settings (admin only).
#     """
#     result = await db.execute(select(User).where(User.id == user_id))
#     user = result.scalar_one_or_none()
    
#     if not user:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="User not found"
#         )
    
#     # Update fields if provided
#     if update_data.first_name is not None:
#         user.first_name = update_data.first_name
#     if update_data.last_name is not None:
#         user.last_name = update_data.last_name
#     if update_data.balance is not None:
#         user.balance = update_data.balance
#     if update_data.is_fake is not None:
#         # Check if user has open positions before changing account type
#         open_trades = await db.execute(
#             select(Trade).where(
#                 and_(
#                     Trade.users_id == user_id,
#                     Trade.status == TradeStatus.EXECUTED
#                 )
#             )
#         )
#         if open_trades.scalars().first():
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="Cannot change account type while user has open positions"
#             )
#         user.is_fake = update_data.is_fake
#     if update_data.is_active is not None:
#         user.is_active = update_data.is_active
    
#     await db.commit()
#     await db.refresh(user)
    
#     return user


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user_profile(
    user_id: UUID,
    update_data: UserUpdate,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_database)
):
    """
    Update user profile settings including leverage (admin only).
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update fields if provided
    if update_data.first_name is not None:
        user.first_name = update_data.first_name
    if update_data.last_name is not None:
        user.last_name = update_data.last_name
    if update_data.balance is not None:
        user.balance = update_data.balance
    
    # NEW: Handle leverage update
    if update_data.leverage is not None:
        # Check if user has open positions before changing leverage
        open_trades = await db.execute(
            select(Trade).where(
                and_(
                    Trade.users_id == user_id,
                    Trade.status == TradeStatus.EXECUTED
                )
            )
        )
        if open_trades.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot change leverage while user has open positions"
            )
        
        old_leverage = user.leverage
        user.leverage = update_data.leverage
        logger.info(f"Admin {admin_user.username} changed leverage for user {user.username} from {old_leverage}:1 to {user.leverage}:1")
    
    if update_data.is_fake is not None:
        # Check if user has open positions before changing account type
        open_trades = await db.execute(
            select(Trade).where(
                and_(
                    Trade.users_id == user_id,
                    Trade.status == TradeStatus.EXECUTED
                )
            )
        )
        if open_trades.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot change account type while user has open positions"
            )
        user.is_fake = update_data.is_fake
        
    if update_data.is_active is not None:
        user.is_active = update_data.is_active
    
    await db.commit()
    await db.refresh(user)
    
    return user

@router.post("/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: UUID,
    new_password: str,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_database)
):
    """
    Reset user password (admin only).
    """
    if len(new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long"
        )
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update password
    user.hashed_password = get_password_hash(new_password)
    
    await db.commit()
    
    return {"message": f"Password reset successfully for user {user.username}"}

@router.post("/users/{user_id}/toggle-status")
async def toggle_user_status(
    user_id: UUID,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_database)
):
    """
    Toggle user active/inactive status (admin only).
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Toggle status
    user.is_active = not user.is_active
    
    await db.commit()
    await db.refresh(user)
    
    status_text = "activated" if user.is_active else "deactivated"
    return {
        "message": f"User {user.username} has been {status_text}",
        "user": user
    }

@router.delete("/users/{user_id}")
async def delete_user_profile(
    user_id: UUID,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_database)
):
    """
    Soft delete user profile (admin only).
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if user has open positions
    open_trades = await db.execute(
        select(Trade).where(
            and_(
                Trade.users_id == user_id,
                Trade.status == TradeStatus.EXECUTED
            )
        )
    )
    
    if open_trades.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete user with open positions. Close all positions first."
        )
    
    # Soft delete
    user.is_deleted = True
    user.is_active = False
    
    await db.commit()
    
    return {"message": f"User {user.username} deleted successfully"}

# ===== DASHBOARD AND STATISTICS =====

@router.get("/dashboard")
async def get_admin_dashboard(
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_database)
):
    """
    Get comprehensive admin dashboard statistics.
    """
    # User statistics
    total_users = await db.execute(select(func.count(User.id)).where(User.is_deleted == False))
    active_users = await db.execute(select(func.count(User.id)).where(and_(User.is_active == True, User.is_deleted == False)))
    admin_users = await db.execute(select(func.count(User.id)).where(and_(User.is_admin == True, User.is_deleted == False)))
    demo_users = await db.execute(select(func.count(User.id)).where(and_(User.is_fake == True, User.is_deleted == False)))
    live_users = await db.execute(select(func.count(User.id)).where(and_(User.is_fake == False, User.is_deleted == False)))
    
    # Trade statistics
    total_trades = await db.execute(select(func.count(Trade.id)))
    real_trades = await db.execute(select(func.count(Trade.id)).where(Trade.is_fake == False))
    demo_trades = await db.execute(select(func.count(Trade.id)).where(Trade.is_fake == True))
    open_trades = await db.execute(select(func.count(Trade.id)).where(Trade.status == TradeStatus.EXECUTED))
    
    # P/L statistics
    total_profit = await db.execute(select(func.sum(Trade.profit)).where(Trade.status == TradeStatus.CLOSED))
    real_profit = await db.execute(select(func.sum(Trade.profit)).where(and_(Trade.status == TradeStatus.CLOSED, Trade.is_fake == False)))
    demo_profit = await db.execute(select(func.sum(Trade.profit)).where(and_(Trade.status == TradeStatus.CLOSED, Trade.is_fake == True)))
    
    # Balance statistics
    total_balance = await db.execute(select(func.sum(User.balance)).where(and_(User.is_deleted == False, User.is_active == True)))
    
    return {
        "users": {
            "total": total_users.scalar() or 0,
            "active": active_users.scalar() or 0,
            "admins": admin_users.scalar() or 0,
            "demo_accounts": demo_users.scalar() or 0,
            "live_accounts": live_users.scalar() or 0
        },
        "trades": {
            "total": total_trades.scalar() or 0,
            "real": real_trades.scalar() or 0,
            "demo": demo_trades.scalar() or 0,
            "open": open_trades.scalar() or 0
        },
        "profit": {
            "total": float(total_profit.scalar() or 0.0),
            "real_only": float(real_profit.scalar() or 0.0),
            "demo_only": float(demo_profit.scalar() or 0.0)
        },
        "financials": {
            "total_user_balance": float(total_balance.scalar() or 0.0)
        }
    }



class LeverageUpdate(BaseModel):
    leverage: int = Field(..., ge=1, le=1000, description="Leverage ratio (1-1000)")
    
    @field_validator('leverage')
    def validate_leverage(cls, v):
        if v < 1 or v > 1000:
            raise ValueError('Leverage must be between 1 and 1000')
        return v

class LeverageResponse(BaseModel):
    user_id: UUID4
    username: str
    leverage: int
    updated_at: datetime
    updated_by: str  # Admin username who made the change

class BulkLeverageUpdate(BaseModel):
    user_ids: List[UUID4] = Field(..., max_items=100, description="List of user IDs (max 100)")
    leverage: int = Field(..., ge=1, le=1000, description="Leverage ratio to apply")

# ===== LEVERAGE MANAGEMENT ENDPOINTS =====

@router.get("/users/{user_id}/leverage", response_model=LeverageResponse)
async def get_user_leverage(
    user_id: UUID,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_database)
):
    """
    Get user's current leverage setting (admin only).
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return LeverageResponse(
        user_id=user.id,
        username=user.username,
        leverage=user.leverage,
        updated_at=user.updated_at or user.created_at,
        updated_by="System"  # You can track this in a separate field if needed
    )

@router.put("/users/{user_id}/leverage", response_model=LeverageResponse)
async def update_user_leverage(
    user_id: UUID,
    leverage_data: LeverageUpdate,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_database)
):
    """
    Update user's leverage setting (admin only).
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if user has open positions before changing leverage
    open_trades = await db.execute(
        select(Trade).where(
            and_(
                Trade.users_id == user_id,
                Trade.status == TradeStatus.EXECUTED
            )
        )
    )
    
    if open_trades.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change leverage while user has open positions. Close all positions first."
        )
    
    # Update leverage
    old_leverage = user.leverage
    user.leverage = leverage_data.leverage
    
    await db.commit()
    await db.refresh(user)
    
    # Log the change (you can implement proper audit logging later)
    logger.info(f"Admin {admin_user.username} changed leverage for user {user.username} from {old_leverage}:1 to {user.leverage}:1")
    
    return LeverageResponse(
        user_id=user.id,
        username=user.username,
        leverage=user.leverage,
        updated_at=user.updated_at,
        updated_by=admin_user.username
    )

@router.post("/users/bulk-leverage", response_model=List[LeverageResponse])
async def bulk_update_leverage(
    bulk_data: BulkLeverageUpdate,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_database)
):
    """
    Update leverage for multiple users at once (admin only).
    """
    if len(bulk_data.user_ids) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update more than 100 users at once"
        )
    
    updated_users = []
    failed_users = []
    
    for user_id in bulk_data.user_ids:
        try:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            
            if not user:
                failed_users.append({
                    "user_id": str(user_id),
                    "error": "User not found"
                })
                continue
            
            # Check for open positions
            open_trades = await db.execute(
                select(Trade).where(
                    and_(
                        Trade.users_id == user_id,
                        Trade.status == TradeStatus.EXECUTED
                    )
                )
            )
            
            if open_trades.scalars().first():
                failed_users.append({
                    "user_id": str(user_id),
                    "username": user.username,
                    "error": "Cannot change leverage while user has open positions"
                })
                continue
            
            # Update leverage
            old_leverage = user.leverage
            user.leverage = bulk_data.leverage
            
            updated_users.append(LeverageResponse(
                user_id=user.id,
                username=user.username,
                leverage=user.leverage,
                updated_at=user.updated_at,
                updated_by=admin_user.username
            ))
            
            logger.info(f"Admin {admin_user.username} changed leverage for user {user.username} from {old_leverage}:1 to {user.leverage}:1")
            
        except Exception as e:
            failed_users.append({
                "user_id": str(user_id),
                "error": str(e)
            })
    
    await db.commit()
    
    # Refresh all updated users
    for response in updated_users:
        result = await db.execute(select(User).where(User.id == response.user_id))
        user = result.scalar_one()
        await db.refresh(user)
    
    if failed_users:
        logger.warning(f"Bulk leverage update completed with errors: {failed_users}")
    
    return updated_users

@router.get("/leverage/statistics")
async def get_leverage_statistics(
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_database)
):
    """
    Get leverage statistics across all users (admin only).
    """
    # Get leverage distribution
    result = await db.execute(
        select(User.leverage, func.count(User.id).label('user_count'))
        .where(and_(User.is_deleted == False, User.is_active == True))
        .group_by(User.leverage)
        .order_by(User.leverage)
    )
    
    leverage_distribution = [
        {"leverage": row.leverage, "user_count": row.user_count}
        for row in result.fetchall()
    ]
    
    # Get average leverage
    avg_result = await db.execute(
        select(func.avg(User.leverage))
        .where(and_(User.is_deleted == False, User.is_active == True))
    )
    avg_leverage = avg_result.scalar() or 0
    
    # Get min/max leverage
    minmax_result = await db.execute(
        select(func.min(User.leverage), func.max(User.leverage))
        .where(and_(User.is_deleted == False, User.is_active == True))
    )
    min_leverage, max_leverage = minmax_result.fetchone()
    
    return {
        "leverage_distribution": leverage_distribution,
        "average_leverage": round(avg_leverage, 2),
        "min_leverage": min_leverage or 0,
        "max_leverage": max_leverage or 0,
        "total_active_users": sum(item["user_count"] for item in leverage_distribution)
    }

@router.post("/users/{user_id}/reset-leverage")
async def reset_user_leverage_to_default(
    user_id: UUID,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_database)
):
    """
    Reset user's leverage to default value (admin only).
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check for open positions
    open_trades = await db.execute(
        select(Trade).where(
            and_(
                Trade.users_id == user_id,
                Trade.status == TradeStatus.EXECUTED
            )
        )
    )
    
    if open_trades.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reset leverage while user has open positions"
        )
    
    old_leverage = user.leverage
    user.leverage = settings.DEFAULT_LEVERAGE
    
    await db.commit()
    await db.refresh(user)
    
    logger.info(f"Admin {admin_user.username} reset leverage for user {user.username} from {old_leverage}:1 to {user.leverage}:1 (default)")
    
    return {
        "message": f"Leverage reset to default ({settings.DEFAULT_LEVERAGE}:1) for user {user.username}",
        "old_leverage": old_leverage,
        "new_leverage": user.leverage
    }