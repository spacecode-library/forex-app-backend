from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Enum as SQLEnum, func, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
import enum
from database import Base

class OrderType(str, enum.Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"

class TradeType(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"

class TradeStatus(str, enum.Enum):
    PENDING = "pending"
    EXECUTED = "executed"
    CLOSED = "closed"
    CANCELLED = "cancelled"

class Trade(Base):
    __tablename__ = "trades"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    users_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    ticket = Column(String(50), unique=True, nullable=False)
    symbol = Column(String(10), nullable=False)
    order_type = Column(SQLEnum(OrderType), nullable=False)
    user_type = Column(SQLEnum(TradeType), nullable=False)  # What user sees
    exec_type = Column(SQLEnum(TradeType), nullable=False)  # What actually executes (reversed)
    margin_required = Column(Float, nullable=True) 
    volume = Column(Float, nullable=False)
    profit = Column(Float, default=0.0)
    status = Column(SQLEnum(TradeStatus), default=TradeStatus.PENDING)
    entry_price = Column(Float)
    exit_price = Column(Float)
    stop_loss = Column(Float)
    take_profit = Column(Float)
    open_time = Column(DateTime(timezone=True), server_default=func.now())
    close_time = Column(DateTime(timezone=True))
    is_fake = Column(Boolean, nullable=False)  # Record if this was fake execution
    gross_profit = Column(Float, nullable=True)  # NEW: Profit before commission
    commission = Column(Float, default=0.0)      
    
    user = relationship("User", back_populates="trades")

