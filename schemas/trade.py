from pydantic import BaseModel, UUID4
from typing import Optional
from datetime import datetime
from models.trade import OrderType, TradeType, TradeStatus

class TradeCreate(BaseModel):
    symbol: str
    order_type: OrderType
    user_type: TradeType
    volume: float
    price: Optional[float] = None  # For limit orders
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

class TradeResponse(BaseModel):
    id: UUID4
    ticket: str
    symbol: str
    order_type: OrderType
    user_type: TradeType
    volume: float
    profit: float
    status: TradeStatus
    entry_price: Optional[float]
    exit_price: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    open_time: datetime
    close_time: Optional[datetime]
    unrealized_pnl: Optional[float] = None
    gross_profit: Optional[float] = None    # NEW
    commission: Optional[float] = None      # NEW
    
    class Config:
        from_attributes = True

class PositionResponse(BaseModel):
    id:UUID4
    symbol: str
    user_type: TradeType
    volume: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    margin_required: Optional[float] = None 
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    open_time: datetime
    status:str

class PriceUpdate(BaseModel):
    symbol: str
    bid: float
    ask: float
    timestamp: datetime

