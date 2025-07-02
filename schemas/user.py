# from pydantic import BaseModel, UUID4
# from typing import Optional
# from datetime import datetime

# class UserBase(BaseModel):
#     first_name: str
#     last_name: str
#     username: str

# class UserCreate(UserBase):
#     password: str
#     is_admin: bool = False
#     balance: float = 10000.0
#     is_fake: bool = True

# class UserUpdate(BaseModel):
#     first_name: Optional[str] = None
#     last_name: Optional[str] = None
#     balance: Optional[float] = None
#     is_fake: Optional[bool] = None
#     is_active: Optional[bool] = None

# class UserResponse(UserBase):
#     id: UUID4
#     is_admin: bool
#     balance: float
#     is_fake: bool
#     is_active: bool
#     created_at: datetime
    
#     class Config:
#         from_attributes = True

# class LoginRequest(BaseModel):
#     username: str
#     password: str

# class Token(BaseModel):
#     access_token: str
#     token_type: str

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
    is_fake: Optional[bool] = Field(default=True, description="Demo account (true) or live account (false)")
    
    @field_validator('password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        return v

class UserUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(None, min_length=1, max_length=50)
    balance: Optional[float] = Field(None, ge=0)
    is_fake: Optional[bool] = None
    is_active: Optional[bool] = None

class UserResponse(UserBase):
    id: UUID4
    is_admin: bool
    balance: float
    is_fake: bool
    is_active: bool
    is_deleted: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class UserListResponse(BaseModel):
    users: List[UserResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

class PasswordReset(BaseModel):
    new_password: str = Field(..., min_length=6, description="New password")
    
    @field_validator('new_password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        return v

class BulkUserCreate(BaseModel):
    users: List[UserCreate] = Field(..., max_items=50, description="List of users to create (max 50)")

class BulkUserResponse(BaseModel):
    created_users: List[UserResponse]
    failed_users: List[dict]
    total_created: int
    total_failed: int
    message: str

class AdminSetupRequest(BaseModel):
    setup_key: str = Field(..., description="Admin setup key")
    admin_data: UserCreate = Field(..., description="Admin user data")
    
    @field_validator('admin_data')
    def ensure_admin_privileges(cls, v):
        v.is_admin = True  # Force admin privileges
        v.is_fake = False  # Admins typically use live accounts
        return v

class UserStats(BaseModel):
    total_users: int
    active_users: int
    admin_users: int
    demo_users: int
    live_users: int
    inactive_users: int
    deleted_users: int

class TradingStats(BaseModel):
    total_trades: int
    real_trades: int
    demo_trades: int
    open_trades: int
    closed_trades: int

class FinancialStats(BaseModel):
    total_profit: float
    real_profit: float
    demo_profit: float
    total_user_balance: float

class AdminDashboardResponse(BaseModel):
    users: UserStats
    trades: TradingStats
    financials: FinancialStats
    system_status: dict = {
        "status": "operational",
        "version": "1.0.0",
        "uptime": "unknown"
    }