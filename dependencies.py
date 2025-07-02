# from fastapi import Depends, HTTPException, status
# from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select
# from database import get_database
# from models.user import User
# from auth.jwt_handler import verify_token

# security = HTTPBearer()

# async def get_current_user(
#     credentials: HTTPAuthorizationCredentials = Depends(security),
#     db: AsyncSession = Depends(get_database)
# ) -> User:
#     """Get current authenticated user"""
#     username = verify_token(credentials.credentials)
#     if not username:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid authentication credentials"
#         )
    
#     result = await db.execute(select(User).where(User.username == username))
#     user = result.scalar_one_or_none()
    
#     if not user or not user.is_active or user.is_deleted:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="User not found or inactive"
#         )
    
#     return user

# async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
#     """Ensure current user is admin"""
#     if not current_user.is_admin:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Admin access required"
#         )
#     return current_user

# # Dependency injection for services
# app.state.price_service = price_service
# app.state.trade_service = trade_service

# # Import routers after app state is set up
# from routers import auth, users, trades, admin
# from websocket.manager import websocket_endpoint

# # Include routers
# app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
# app.include_router(users.router, prefix="/api/users", tags=["Users"])
# app.include_router(trades.router, prefix="/api/trades", tags=["Trading"])
# app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])

# # WebSocket endpoint
# app.websocket("/ws")(websocket_endpoint)

# # Health check
# @app.get("/health")
# async def health_check():
#     return {"status": "healthy"}

# # Dependency injection for services
# app.state.price_service = price_service
# app.state.trade_service = trade_service

# if __name__ == "__main__":
#     uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_database
from models.user import User
from auth.jwt_handler import verify_token
from services.price_service import PriceService
from services.trade_service import TradeService

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_database)
) -> User:
    username = verify_token(credentials.credentials)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if not user or not user.is_active or user.is_deleted:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    
    return user

async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

def get_price_service(request: Request) -> PriceService:
    return request.app.state.price_service

def get_trade_service(request: Request) -> TradeService:
    return request.app.state.trade_service
