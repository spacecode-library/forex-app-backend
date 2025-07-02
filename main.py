# from fastapi import FastAPI, Depends, HTTPException, status
# from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# from fastapi.middleware.cors import CORSMiddleware
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select
# import uvicorn
# import asyncio
# from contextlib import asynccontextmanager
# from fastapi import Depends, HTTPException, status

# from database import get_database, create_tables
# from models.user import User
# from auth.jwt_handler import verify_token
# from services.price_service import PriceService
# from services.trade_service import TradeService

# # We'll import these after the app is created to avoid circular imports

# # Initialize services
# price_service = PriceService()
# trade_service = TradeService(price_service)

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     # Startup
#     await create_tables()
#     await price_service.start_price_feed()
#     yield
#     # Shutdown
#     await price_service.mt5_service.disconnect()

# app = FastAPI(
#     title="Trading Platform API",
#     description="FastAPI backend for MetaTrader 5-like trading platform",
#     version="1.0.0",
#     lifespan=lifespan
# )

# # CORS middleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

from fastapi import FastAPI
from contextlib import asynccontextmanager
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from services.price_service import PriceService
from services.trade_service import TradeService
from database import create_tables

# Initialize services
price_service = PriceService()
trade_service = TradeService(price_service)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    await price_service.start_price_feed()
    yield
    await price_service.mt5_service.disconnect()

app = FastAPI(
    title="Trading Platform API",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Register services on app state
app.state.price_service = price_service
app.state.trade_service = trade_service

# Add CORS middleware here...

# ✅ Import and include routers AFTER setting up app and services
from routers import auth, users, trades, admin
from websocket.manager import websocket_endpoint

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(trades.router, prefix="/api/trades", tags=["Trading"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])

# WebSocket route
app.websocket("/ws")(websocket_endpoint)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
