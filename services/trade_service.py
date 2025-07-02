from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional
import uuid
from datetime import datetime
import logging

from models.trade import Trade, TradeStatus, TradeType
from models.user import User
from schemas.trade import TradeCreate, PositionResponse
from services.mt5_service import MT5Service
from services.price_service import PriceService

logger = logging.getLogger(__name__)

class TradeService:
    def __init__(self, price_service: PriceService):
        self.mt5_service = MT5Service()
        self.price_service = price_service
    
    async def place_trade(self, db: AsyncSession, user: User, trade_data: TradeCreate) -> Trade:
        """Place a new trade"""
        # Generate unique ticket
        ticket = str(uuid.uuid4())[:8].upper()
        
        # Reverse the execution type (user buys, we sell to market)
        exec_type = TradeType.SELL if trade_data.user_type == TradeType.BUY else TradeType.BUY
        
        # Create trade record
        trade = Trade(
            users_id=user.id,
            ticket=ticket,
            symbol=trade_data.symbol,
            order_type=trade_data.order_type,
            user_type=trade_data.user_type,
            exec_type=exec_type,
            volume=trade_data.volume,
            stop_loss=trade_data.stop_loss,
            take_profit=trade_data.take_profit,
            is_fake=user.is_fake,
            status=TradeStatus.PENDING
        )
        
        try:
            if user.is_fake:
                # Fake execution - simulate immediately
                await self._execute_fake_trade(trade)
            else:
                # Real execution - send to MT5
                await self._execute_real_trade(trade)
            
            # Deduct margin from user balance (simplified)
            margin_required = trade_data.volume * 1000  # Simplified margin calculation
            user.balance -= margin_required
            
            db.add(trade)
            await db.commit()
            await db.refresh(trade)
            
            return trade
            
        except Exception as e:
            logger.error(f"Trade execution error: {e}")
            trade.status = TradeStatus.CANCELLED
            db.add(trade)
            await db.commit()
            raise
    
    async def _execute_fake_trade(self, trade: Trade):
        """Execute fake trade using current market price"""
        price_data = await self.price_service.get_price(trade.symbol)
        if not price_data:
            raise Exception(f"No price data available for {trade.symbol}")
        
        # Use bid for sell execution, ask for buy execution
        if trade.exec_type == TradeType.SELL:
            trade.entry_price = price_data["bid"]
        else:
            trade.entry_price = price_data["ask"]
        
        trade.status = TradeStatus.EXECUTED
        logger.info(f"Fake trade executed: {trade.ticket} at {trade.entry_price}")
    
    async def _execute_real_trade(self, trade: Trade):
        """Execute real trade via MT5"""
        result = await self.mt5_service.place_order(
            symbol=trade.symbol,
            order_type=trade.exec_type.value,
            volume=trade.volume,
            sl=trade.stop_loss,
            tp=trade.take_profit
        )
        
        if not result:
            raise Exception("MT5 order execution failed")
        
        trade.entry_price = result["price"]
        trade.ticket = result["ticket"]
        trade.status = TradeStatus.EXECUTED
        logger.info(f"Real trade executed: {trade.ticket} at {trade.entry_price}")
    
    async def close_trade(self, db: AsyncSession, trade: Trade) -> Trade:
        """Close an open trade"""
        if trade.status != TradeStatus.EXECUTED:
            raise Exception("Trade is not open")
        
        try:
            if trade.is_fake:
                await self._close_fake_trade(trade)
            else:
                await self._close_real_trade(trade)
            
            # Calculate profit and update user balance
            user_result = await db.execute(select(User).where(User.id == trade.users_id))
            user = user_result.scalar_one()
            
            # Add profit and release margin
            margin_released = trade.volume * 1000
            user.balance += margin_released + trade.profit
            
            trade.status = TradeStatus.CLOSED
            trade.close_time = datetime.now()
            
            await db.commit()
            return trade
            
        except Exception as e:
            logger.error(f"Trade close error: {e}")
            raise
    
    async def _close_fake_trade(self, trade: Trade):
        """Close fake trade using current market price"""
        price_data = await self.price_service.get_price(trade.symbol)
        if not price_data:
            raise Exception(f"No price data available for {trade.symbol}")
        
        # Use bid for buy closing, ask for sell closing
        if trade.exec_type == TradeType.SELL:
            trade.exit_price = price_data["ask"]
        else:
            trade.exit_price = price_data["bid"]
        
        # Calculate profit based on execution side
        if trade.exec_type == TradeType.SELL:
            # We sold, profit when price goes down
            price_diff = trade.entry_price - trade.exit_price
        else:
            # We bought, profit when price goes up
            price_diff = trade.exit_price - trade.entry_price
        
        trade.profit = price_diff * trade.volume * 1000  # Simplified P/L calculation
    
    async def _close_real_trade(self, trade: Trade):
        """Close real trade via MT5"""
        result = await self.mt5_service.close_position(
            ticket=trade.ticket,
            symbol=trade.symbol,
            volume=trade.volume,
            position_type=trade.exec_type.value
        )
        
        if not result:
            raise Exception("MT5 position close failed")
        
        trade.exit_price = result["price"]
        
        # Calculate profit (similar to fake trade)
        if trade.exec_type == TradeType.SELL:
            price_diff = trade.entry_price - trade.exit_price
        else:
            price_diff = trade.exit_price - trade.entry_price
        
        trade.profit = price_diff * trade.volume * 1000
    
    async def get_open_positions(self, db: AsyncSession, user_id: str) -> List[PositionResponse]:
        """Get all open positions for a user"""
        result = await db.execute(
            select(Trade).where(
                and_(
                    Trade.users_id == user_id,
                    Trade.status == TradeStatus.EXECUTED
                )
            )
        )
        trades = result.scalars().all()
        
        positions = []
        for trade in trades:
            # Get current price for unrealized P/L
            price_data = await self.price_service.get_price(trade.symbol)
            if price_data:
                current_price = price_data["bid"] if trade.exec_type == TradeType.SELL else price_data["ask"]
                
                # Calculate unrealized P/L
                if trade.exec_type == TradeType.SELL:
                    unrealized_pnl = (trade.entry_price - current_price) * trade.volume * 1000
                else:
                    unrealized_pnl = (current_price - trade.entry_price) * trade.volume * 1000
                
                positions.append(PositionResponse(
                    id=trade.id,
                    symbol=trade.symbol,
                    user_type=trade.user_type,
                    volume=trade.volume,
                    entry_price=trade.entry_price,
                    current_price=current_price,
                    unrealized_pnl=unrealized_pnl,
                    open_time=trade.open_time,
                    status='EXECUTED' 
                ))
        
        return positions