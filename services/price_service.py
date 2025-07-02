import asyncio
import json
from typing import Dict, List, Optional
from datetime import datetime
import logging
from config import settings
from services.mt5_service import MT5Service
from schemas.trade import PriceUpdate

logger = logging.getLogger(__name__)

class PriceService:
    def __init__(self):
        self.mt5_service = MT5Service()
        self.prices: Dict[str, Dict] = {}
        self.subscribers: List = []
    
    async def start_price_feed(self):
        """Start background task to fetch prices"""
        await self.mt5_service.connect()
        asyncio.create_task(self._price_update_loop())


    async def _price_update_loop(self):
        """Background loop to update prices"""
        while True:
            try:
                for symbol in settings.SYMBOLS:
                    price_data = await self.mt5_service.get_symbol_price(symbol)
                    if price_data:
                        price_update = PriceUpdate(
                            symbol=symbol,
                            bid=price_data["bid"],
                            ask=price_data["ask"],
                            timestamp=datetime.now()
                        )
                        
                                                
                        # Store locally
                        self.prices[symbol] = price_update.dict()
                        
                        # Notify WebSocket subscribers
                        await self._notify_subscribers(price_update)

                        # NEW: Recalculate and broadcast position updates
                        await self._update_positions_for_symbol(symbol, price_data)
                
                await asyncio.sleep(1)  # Update every second
                
            except Exception as e:
                logger.error(f"Price update error: {e}")
                await asyncio.sleep(5)



    async def _update_positions_for_symbol(self, symbol: str, price_data: dict):
        """Recalculate positions for a symbol and broadcast updates"""
        try:
            from database import async_session
            from models.trade import Trade, TradeStatus
            from sqlalchemy import select, and_
            
            async with async_session() as db:
                # Get all open positions for this symbol
                result = await db.execute(
                    select(Trade).where(
                        and_(
                            Trade.symbol == symbol,
                            Trade.status == TradeStatus.EXECUTED
                        )
                    )
                )
                open_trades = result.scalars().all()
                
                for trade in open_trades:
                    # Calculate current price and unrealized P&L
                    current_price = price_data["bid"] if trade.exec_type.value == "sell" else price_data["ask"]
                    
                    if trade.exec_type.value == "sell":
                        unrealized_pnl = (trade.entry_price - current_price) * trade.volume * 1000
                    else:
                        unrealized_pnl = (current_price - trade.entry_price) * trade.volume * 1000
                    
                    # Create position update message
                    position_update = {
                        "type": "position_update",
                        "data": {
                            "id": str(trade.id),
                            "symbol": trade.symbol,
                            "user_type": trade.user_type.value,
                            "volume": trade.volume,
                            "entry_price": trade.entry_price,
                            "current_price": current_price,
                            "unrealized_pnl": unrealized_pnl,
                            "open_time": trade.open_time.isoformat(),
                            "status": trade.status.value
                        }
                    }
                    # print(position_update)
                    # Broadcast to WebSocket subscribers
                    await self._notify_subscribers_position_update(position_update)
                    
        except Exception as e:
            logger.error(f"Position update error for {symbol}: {e}")
                    
    async def _notify_subscribers_position_update(self, position_update):
        """Notify WebSocket subscribers of position updates"""
        if not self.subscribers:
            return
        
        # Remove disconnected subscribers
        active_subscribers = []
        for websocket in self.subscribers:
            try:
                await websocket.send_text(json.dumps(position_update, default=str))
                active_subscribers.append(websocket)
            except:
                pass  # WebSocket disconnected
        
        self.subscribers = active_subscribers       
        
    async def get_price(self, symbol: str) -> Optional[Dict]:
        """Get current price for symbol"""
        
        # Fallback to MT5
        price_data = await self.mt5_service.get_symbol_price(symbol)
        if price_data:
            return {
                "symbol": symbol,
                "bid": price_data["bid"],
                "ask": price_data["ask"],
                "timestamp": datetime.now()
            }
        
        return None
    
    def add_subscriber(self, websocket):
        """Add WebSocket subscriber for price updates"""
        self.subscribers.append(websocket)
    
    def remove_subscriber(self, websocket):
        """Remove WebSocket subscriber"""
        if websocket in self.subscribers:
            self.subscribers.remove(websocket)
    
    async def _notify_subscribers(self, price_update: PriceUpdate):
        """Notify all WebSocket subscribers of price update"""
        if not self.subscribers:
            return
        
        message = {
            "type": "price_update",
            "data": price_update.dict()
        }
        
        # Remove disconnected subscribers
        active_subscribers = []
        for websocket in self.subscribers:
            try:
                await websocket.send_text(json.dumps(message, default=str))
                active_subscribers.append(websocket)
            except:
                pass  # WebSocket disconnected
        
        self.subscribers = active_subscribers

