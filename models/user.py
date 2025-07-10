# from sqlalchemy import Column, String, Boolean, Float, DateTime, func
# from sqlalchemy.dialects.postgresql import UUID
# from sqlalchemy.orm import relationship
# import uuid
# from database import Base

# class User(Base):
#     __tablename__ = "users"
    
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     first_name = Column(String(50), nullable=False)
#     last_name = Column(String(50), nullable=False)
#     username = Column(String(50), unique=True, nullable=False)
#     hashed_password = Column(String(255), nullable=False)
#     is_admin = Column(Boolean, default=False)
#     balance = Column(Float, default=10000.0)
#     is_fake = Column(Boolean, default=True)  # Default to fake trading
#     is_active = Column(Boolean, default=True)
#     is_deleted = Column(Boolean, default=False)
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
#     updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
#     trades = relationship("Trade", back_populates="user")

# ===== UPDATE models/user.py =====

from sqlalchemy import Column, String, Boolean, Float, DateTime, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from database import Base
from config import settings

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    username = Column(String(50), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False)
    balance = Column(Float, default=10000.0)
    leverage = Column(Integer, default=settings.DEFAULT_LEVERAGE)  # NEW: Leverage field
    is_fake = Column(Boolean, default=True)  # Default to fake trading
    is_active = Column(Boolean, default=True)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    trades = relationship("Trade", back_populates="user")

# ===== UPDATE schemas/user.py =====

from pydantic import BaseModel, UUID4, field_validator, Field
from typing import Optional, List
from datetime import datetime

class UserBase(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=50, description="User's first name")
    last_name: str = Field(..., min_length=1, max_length=50, description="User's last name")
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    
    @field_validator('username')
    def validate_username(cls, v):
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username can only contain letters, numbers, hyphens, and underscores')
        return v.lower()

class UserCreate(UserBase):
    password: str = Field(..., min_length=6, description="User password (minimum 6 characters)")
    is_admin: Optional[bool] = Field(default=False, description="Admin privileges")
    balance: Optional[float] = Field(default=10000.0, ge=0, description="Initial account balance")
    leverage: Optional[int] = Field(default=100, ge=1, le=1000, description="Trading leverage (1-1000)")  # NEW
    is_fake: Optional[bool] = Field(default=True, description="Demo account (true) or live account (false)")
    
    @field_validator('password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        return v
    
    @field_validator('leverage')
    def validate_leverage(cls, v):
        if v < 1 or v > 1000:
            raise ValueError('Leverage must be between 1 and 1000')
        return v

class UserUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(None, min_length=1, max_length=50)
    balance: Optional[float] = Field(None, ge=0)
    leverage: Optional[int] = Field(None, ge=1, le=1000, description="Trading leverage (1-1000)")  # NEW
    is_fake: Optional[bool] = None
    is_active: Optional[bool] = None
    
    @field_validator('leverage')
    def validate_leverage(cls, v):
        if v is not None and (v < 1 or v > 1000):
            raise ValueError('Leverage must be between 1 and 1000')
        return v

class UserResponse(UserBase):
    id: UUID4
    is_admin: bool
    balance: float
    leverage: int  # NEW: Include leverage in response
    is_fake: bool
    is_active: bool
    is_deleted: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# ===== NEW LEVERAGE-SPECIFIC SCHEMAS =====

