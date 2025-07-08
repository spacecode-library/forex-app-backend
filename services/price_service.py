# import asyncio
# import json
# from typing import Dict, List, Optional
# from datetime import datetime
# import logging
# from config import settings
# from services.mt5_service import MT5Service
# from schemas.trade import PriceUpdate

# logger = logging.getLogger(__name__)

# class PriceService:
#     def __init__(self):
#         self.mt5_service = MT5Service()
#         self.prices: Dict[str, Dict] = {}
#         self.subscribers: List = []
    
#     async def start_price_feed(self):
#         """Start background task to fetch prices"""
#         await self.mt5_service.connect()
#         asyncio.create_task(self._price_update_loop())


#     async def _price_update_loop(self):
#         """Background loop to update prices"""
#         while True:
#             try:
#                 for symbol in settings.SYMBOLS:
#                     price_data = await self.mt5_service.get_symbol_price(symbol)
#                     if price_data:
#                         price_update = PriceUpdate(
#                             symbol=symbol,
#                             bid=price_data["bid"],
#                             ask=price_data["ask"],
#                             timestamp=datetime.now()
#                         )
                        
                                                
#                         # Store locally
#                         self.prices[symbol] = price_update.dict()
                        
#                         # Notify WebSocket subscribers
#                         await self._notify_subscribers(price_update)

#                         # NEW: Recalculate and broadcast position updates
#                         await self._update_positions_for_symbol(symbol, price_data)
                
#                 await asyncio.sleep(1)  # Update every second
                
#             except Exception as e:
#                 logger.error(f"Price update error: {e}")
#                 await asyncio.sleep(5)



#     async def _update_positions_for_symbol(self, symbol: str, price_data: dict):
#         """Recalculate positions for a symbol and broadcast updates"""
#         try:
#             from database import async_session
#             from models.trade import Trade, TradeStatus
#             from sqlalchemy import select, and_
            
#             async with async_session() as db:
#                 # Get all open positions for this symbol
#                 result = await db.execute(
#                     select(Trade).where(
#                         and_(
#                             Trade.symbol == symbol,
#                             Trade.status == TradeStatus.EXECUTED
#                         )
#                     )
#                 )
#                 open_trades = result.scalars().all()
                
#                 for trade in open_trades:
#                     # Calculate current price and unrealized P&L
#                     current_price = price_data["bid"] if trade.exec_type.value == "sell" else price_data["ask"]
                    
#                     if trade.exec_type.value == "sell":
#                         unrealized_pnl = (trade.entry_price - current_price) * trade.volume * 1000
#                     else:
#                         unrealized_pnl = (current_price - trade.entry_price) * trade.volume * 1000
                    
#                     # Create position update message
#                     position_update = {
#                         "type": "position_update",
#                         "data": {
#                             "id": str(trade.id),
#                             "symbol": trade.symbol,
#                             "user_type": trade.user_type.value,
#                             "volume": trade.volume,
#                             "entry_price": trade.entry_price,
#                             "current_price": current_price,
#                             "unrealized_pnl": unrealized_pnl,
#                             "open_time": trade.open_time.isoformat(),
#                             "status": trade.status.value
#                         }
#                     }
#                     # print(position_update)
#                     # Broadcast to WebSocket subscribers
#                     await self._notify_subscribers_position_update(position_update)
                    
#         except Exception as e:
#             logger.error(f"Position update error for {symbol}: {e}")
                    
#     async def _notify_subscribers_position_update(self, position_update):
#         """Notify WebSocket subscribers of position updates"""
#         if not self.subscribers:
#             return
        
#         # Remove disconnected subscribers
#         active_subscribers = []
#         for websocket in self.subscribers:
#             try:
#                 await websocket.send_text(json.dumps(position_update, default=str))
#                 active_subscribers.append(websocket)
#             except:
#                 pass  # WebSocket disconnected
        
#         self.subscribers = active_subscribers       
        
#     async def get_price(self, symbol: str) -> Optional[Dict]:
#         """Get current price for symbol"""
        
#         # Fallback to MT5
#         price_data = await self.mt5_service.get_symbol_price(symbol)
#         if price_data:
#             return {
#                 "symbol": symbol,
#                 "bid": price_data["bid"],
#                 "ask": price_data["ask"],
#                 "timestamp": datetime.now()
#             }
        
#         return None
    
#     def add_subscriber(self, websocket):
#         """Add WebSocket subscriber for price updates"""
#         self.subscribers.append(websocket)
    
#     def remove_subscriber(self, websocket):
#         """Remove WebSocket subscriber"""
#         if websocket in self.subscribers:
#             self.subscribers.remove(websocket)
    
#     async def _notify_subscribers(self, price_update: PriceUpdate):
#         """Notify all WebSocket subscribers of price update"""
#         if not self.subscribers:
#             return
        
#         message = {
#             "type": "price_update",
#             "data": price_update.dict()
#         }
        
#         # Remove disconnected subscribers
#         active_subscribers = []
#         for websocket in self.subscribers:
#             try:
#                 await websocket.send_text(json.dumps(message, default=str))
#                 active_subscribers.append(websocket)
#             except:
#                 pass  # WebSocket disconnected
        
#         self.subscribers = active_subscribers



# import asyncio
# import json
# from typing import Dict, List, Optional
# from datetime import datetime
# import logging
# from config import settings
# from services.mt5_service import MT5Service
# from schemas.trade import PriceUpdate

# logger = logging.getLogger(__name__)

# class PriceService:
#     def __init__(self):
#         self.mt5_service = MT5Service()
#         self.prices: Dict[str, Dict] = {}
#         self.daily_stats: Dict[str, Dict] = {}
#         self.subscribers: List = []
#         self.last_reset_date = datetime.now().date()
#         # Cache for open positions to avoid database calls during price updates
#         self.cached_positions: Dict[str, List] = {}  # symbol -> list of positions
#         self.last_position_cache_update = datetime.now()
#         self.cache_update_interval = 30  # seconds
    
#     async def start_price_feed(self):
#         """Start background task to fetch prices"""
#         await self.mt5_service.connect()
#         self._reset_daily_stats()
        
#         # Start price update loop
#         asyncio.create_task(self._price_update_loop())
        
#         # Start position cache update loop
#         asyncio.create_task(self._position_cache_update_loop())

#     async def _price_update_loop(self):
#         """Background loop to update prices and calculate position P&L"""
#         while True:
#             try:
#                 current_date = datetime.now().date()
#                 if current_date != self.last_reset_date:
#                     self._reset_daily_stats()
#                     self.last_reset_date = current_date
                
#                 for symbol in settings.SYMBOLS:
#                     price_data = await self.mt5_service.get_symbol_price(symbol)
#                     if price_data:
#                         # Calculate change from daily open
#                         previous_price = self.prices.get(symbol, {})
#                         daily_open = self.daily_stats.get(symbol, {}).get('open', price_data["bid"])
                        
#                         change = price_data["bid"] - daily_open
#                         change_percent = (change / daily_open * 100) if daily_open != 0 else 0
                        
#                         # Update daily stats
#                         self._update_daily_stats(symbol, price_data["bid"], price_data["ask"])
                        
#                         # Enhanced price data
#                         enhanced_price_data = {
#                             "symbol": symbol,
#                             "bid": price_data["bid"],
#                             "ask": price_data["ask"],
#                             "timestamp": datetime.now().isoformat(),
#                             "high": self.daily_stats[symbol]["high"],
#                             "low": self.daily_stats[symbol]["low"],
#                             "change": change,
#                             "change_percent": change_percent,
#                             "spread": price_data["ask"] - price_data["bid"],
#                             "volume": price_data.get("volume", 0)
#                         }
                        
#                         # Store locally
#                         self.prices[symbol] = enhanced_price_data
                        
#                         # Notify WebSocket subscribers of price update
#                         await self._notify_price_update(enhanced_price_data)

#                         # 🚀 REAL-TIME P&L: Calculate and broadcast position updates
#                         await self._calculate_and_broadcast_position_pnl(symbol, price_data["bid"], price_data["ask"])
                        
#                 await asyncio.sleep(1)  # Update every second
                
#             except Exception as e:
#                 logger.error(f"Price update loop error: {e}")
#                 await asyncio.sleep(5)

#     async def _position_cache_update_loop(self):
#         """Periodically update position cache from database"""
#         while True:
#             try:
#                 await self._update_position_cache()
#                 await asyncio.sleep(self.cache_update_interval)
#             except Exception as e:
#                 logger.error(f"Position cache update error: {e}")
#                 await asyncio.sleep(self.cache_update_interval)

#     async def _update_position_cache(self):
#         """Update cached positions from database"""
#         try:
#             from main import app
#             from database import get_database
#             from sqlalchemy import select
#             from models.trade import Trade, TradeStatus
            
#             # Get database session
#             async with get_database() as db:
#                 # Fetch all open positions
#                 result = await db.execute(
#                     select(Trade).where(Trade.status == TradeStatus.EXECUTED)
#                 )
#                 open_trades = result.scalars().all()
                
#                 # Group by symbol
#                 new_cache = {}
#                 for trade in open_trades:
#                     if trade.symbol not in new_cache:
#                         new_cache[trade.symbol] = []
#                     new_cache[trade.symbol].append(trade)
                
#                 self.cached_positions = new_cache
#                 self.last_position_cache_update = datetime.now()
                
#                 total_positions = sum(len(positions) for positions in new_cache.values())
#                 logger.debug(f"Position cache updated: {total_positions} positions across {len(new_cache)} symbols")
                
#         except Exception as e:
#             logger.error(f"Failed to update position cache: {e}")

#     async def _calculate_and_broadcast_position_pnl(self, symbol: str, bid: float, ask: float):
#         """Calculate P&L for all positions of a symbol and broadcast updates"""
#         try:
#             # Get positions from cache
#             positions = self.cached_positions.get(symbol, [])
            
#             if not positions:
#                 return
            
#             logger.debug(f"💰 Calculating P&L for {len(positions)} {symbol} positions")
            
#             for trade in positions:
#                 try:
#                     # Determine current price based on trade type
#                     current_price = bid if trade.user_type.value == 'sell' else ask
                    
#                     # Calculate unrealized P&L
#                     if trade.user_type.value == 'buy':
#                         price_diff = current_price - trade.entry_price
#                     else:
#                         price_diff = trade.entry_price - current_price
                    
#                     # Calculate P&L based on symbol specifications
#                     point_value = self._get_point_value(symbol)
#                     unrealized_pnl = price_diff * trade.volume * 1000 * point_value
                    
#                     # Calculate pips
#                     pips = self._calculate_pips(symbol, trade.entry_price, current_price, trade.user_type.value)
                    
#                     # Create position update message
#                     position_update = {
#                         "type": "position_update",
#                         "data": {
#                             "id": str(trade.id),
#                             "symbol": trade.symbol,
#                             "user_type": trade.user_type.value,
#                             "volume": trade.volume,
#                             "entry_price": trade.entry_price,
#                             "current_price": current_price,
#                             "unrealized_pnl": round(unrealized_pnl, 2),
#                             "price_diff": round(price_diff, 5),
#                             "pips": round(pips, 1),
#                             "open_time": trade.open_time.isoformat(),
#                             "status": trade.status.value,
#                             "timestamp": datetime.now().isoformat()
#                         }
#                     }
                    
#                     # Broadcast to WebSocket subscribers
#                     await self._notify_position_update(position_update)
                    
#                 except Exception as e:
#                     logger.error(f"Error calculating P&L for trade {trade.id}: {e}")
                    
#         except Exception as e:
#             logger.error(f"Position P&L calculation error for {symbol}: {e}")

#     def _get_point_value(self, symbol: str) -> float:
#         """Get point value for P&L calculations"""
#         if "JPY" in symbol:
#             return 0.01  # 1 pip = 0.01 for JPY pairs
#         elif symbol == "XAUUSD":
#             return 0.1   # 1 pip = $0.10 for Gold per 0.01 move
#         else:
#             return 1     # 1 pip = $1 for major pairs per 0.0001 move

#     def _calculate_pips(self, symbol: str, entry_price: float, current_price: float, trade_type: str) -> float:
#         """Calculate pips gained/lost"""
#         if trade_type == 'buy':
#             price_diff = current_price - entry_price
#         else:
#             price_diff = entry_price - current_price
        
#         if "JPY" in symbol:
#             return price_diff * 100
#         elif symbol == "XAUUSD":
#             return price_diff * 10
#         else:
#             return price_diff * 10000

#     def _reset_daily_stats(self):
#         """Reset daily statistics"""
#         logger.info("Resetting daily price statistics")
#         for symbol in settings.SYMBOLS:
#             if symbol in self.prices:
#                 current_price = self.prices[symbol]
#                 self.daily_stats[symbol] = {
#                     "open": current_price.get("bid", 0),
#                     "high": current_price.get("ask", 0),
#                     "low": current_price.get("bid", 0),
#                     "volume": 0
#                 }
#             else:
#                 self.daily_stats[symbol] = {
#                     "open": 0,
#                     "high": 0,
#                     "low": float('inf'),
#                     "volume": 0
#                 }

#     def _update_daily_stats(self, symbol: str, bid: float, ask: float):
#         """Update daily high/low statistics"""
#         if symbol not in self.daily_stats:
#             self.daily_stats[symbol] = {
#                 "open": bid,
#                 "high": ask,
#                 "low": bid,
#                 "volume": 0
#             }
#         else:
#             stats = self.daily_stats[symbol]
#             stats["high"] = max(stats["high"], ask)
#             stats["low"] = min(stats["low"], bid)
#             stats["volume"] += 1

#     async def _notify_price_update(self, price_data: Dict):
#         """Notify subscribers of price updates"""
#         if not self.subscribers:
#             return
        
#         message = {
#             "type": "price_update",
#             "data": price_data
#         }
        
#         await self._broadcast_message(message)

#     async def _notify_position_update(self, position_update: Dict):
#         """Notify subscribers of position P&L updates"""
#         if not self.subscribers:
#             return
        
#         await self._broadcast_message(position_update)

#     async def _broadcast_message(self, message: Dict):
#         """Broadcast message to all connected WebSocket clients"""
#         if not self.subscribers:
#             return
        
#         active_subscribers = []
#         message_str = json.dumps(message, default=str)
        
#         for websocket in self.subscribers:
#             try:
#                 await websocket.send_text(message_str)
#                 active_subscribers.append(websocket)
#             except Exception as e:
#                 logger.debug(f"WebSocket send failed: {e}")
#                 pass  # WebSocket disconnected
        
#         self.subscribers = active_subscribers

#     async def get_price(self, symbol: str) -> Optional[Dict]:
#         """Get current price for symbol"""
#         if symbol in self.prices:
#             return self.prices[symbol]
        
#         # Fallback to MT5
#         price_data = await self.mt5_service.get_symbol_price(symbol)
#         if price_data:
#             return {
#                 "symbol": symbol,
#                 "bid": price_data["bid"],
#                 "ask": price_data["ask"],
#                 "timestamp": datetime.now().isoformat(),
#                 "spread": price_data["ask"] - price_data["bid"]
#             }
        
#         return None

#     def add_subscriber(self, websocket):
#         """Add WebSocket subscriber"""
#         self.subscribers.append(websocket)
#         logger.info(f"WebSocket subscriber added. Total: {len(self.subscribers)}")

#     def remove_subscriber(self, websocket):
#         """Remove WebSocket subscriber"""
#         if websocket in self.subscribers:
#             self.subscribers.remove(websocket)
#             logger.info(f"WebSocket subscriber removed. Total: {len(self.subscribers)}")

#     # 🆕 Manual cache refresh (can be called from API endpoints)
#     async def refresh_position_cache(self):
#         """Manually refresh position cache"""
#         await self._update_position_cache()
#         logger.info("Position cache manually refreshed")

#     # 🆕 Get cache statistics
#     def get_cache_stats(self):
#         """Get position cache statistics"""
#         total_positions = sum(len(positions) for positions in self.cached_positions.values())
#         return {
#             "symbols": len(self.cached_positions),
#             "total_positions": total_positions,
#             "last_update": self.last_position_cache_update.isoformat(),
#             "cache_age_seconds": (datetime.now() - self.last_position_cache_update).total_seconds()
#         }# services/price_service.py - FIXED VERSION

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
        self.daily_stats: Dict[str, Dict] = {}
        self.subscribers: List = []
        self.last_reset_date = datetime.now().date()
        # Cache for open positions to avoid database calls during price updates
        self.cached_positions: Dict[str, List] = {}  # symbol -> list of positions
        self.last_position_cache_update = datetime.now()
        self.cache_update_interval = 30  # seconds
        
        # Reference to trade service for order monitoring
        self.trade_service = None
    
    def set_trade_service(self, trade_service):
        """Set reference to trade service for order monitoring"""
        self.trade_service = trade_service
    
    async def start_price_feed(self):
        """Start background task to fetch prices"""
        await self.mt5_service.connect()
        self._reset_daily_stats()
        
        # Start price update loop
        asyncio.create_task(self._price_update_loop())
        
        # Start position cache update loop
        asyncio.create_task(self._position_cache_update_loop())
        
        # Start order monitoring loop (for limit orders and SL/TP on our backend)
        asyncio.create_task(self._order_monitoring_loop())

    async def _price_update_loop(self):
        """Background loop to update prices and calculate position P&L"""
        while True:
            try:
                current_date = datetime.now().date()
                if current_date != self.last_reset_date:
                    self._reset_daily_stats()
                    self.last_reset_date = current_date
                
                for symbol in ["EURUSD", "USDJPY", "XAUUSD"]:  # Only monitor these 3 symbols
                    price_data = await self.mt5_service.get_symbol_price(symbol)
                    if price_data:
                        # Calculate change from daily open
                        previous_price = self.prices.get(symbol, {})
                        daily_open = self.daily_stats.get(symbol, {}).get('open', price_data["bid"])
                        
                        change = price_data["bid"] - daily_open
                        change_percent = (change / daily_open * 100) if daily_open != 0 else 0
                        
                        # Update daily stats
                        self._update_daily_stats(symbol, price_data["bid"], price_data["ask"])
                        
                        # Enhanced price data
                        enhanced_price_data = {
                            "symbol": symbol,
                            "bid": price_data["bid"],
                            "ask": price_data["ask"],
                            "timestamp": datetime.now().isoformat(),
                            "high": self.daily_stats[symbol]["high"],
                            "low": self.daily_stats[symbol]["low"],
                            "change": change,
                            "change_percent": change_percent,
                            "spread": price_data["ask"] - price_data["bid"],
                            "volume": price_data.get("volume", 0)
                        }
                        
                        # Store locally
                        self.prices[symbol] = enhanced_price_data
                        
                        # Notify WebSocket subscribers of price update
                        await self._notify_price_update(enhanced_price_data)

                        # Calculate and broadcast position updates with correct user P&L
                        await self._calculate_and_broadcast_position_pnl(symbol, price_data["bid"], price_data["ask"])
                        
                await asyncio.sleep(1)  # Update every second
                
            except Exception as e:
                logger.error(f"Price update loop error: {e}")
                await asyncio.sleep(5)

    async def _order_monitoring_loop(self):
        """✅ FIXED: Monitor pending orders and positions for execution/SL/TP triggers"""
        while True:
            try:
                if self.trade_service:
                    from database import get_database
                    
                    # ✅ FIXED: Use async generator correctly
                    async for db in get_database():
                        try:
                            # Monitor pending limit orders
                            await self.trade_service.monitor_pending_orders(db)
                            
                            # Monitor stop loss and take profit
                            await self.trade_service.monitor_stop_loss_take_profit(db)
                            
                            break  # Exit the async for loop after successful execution
                        except Exception as e:
                            logger.error(f"Database operation error in monitoring: {e}")
                            break
                
                await asyncio.sleep(1)  # Check every second for precise execution
                
            except Exception as e:
                logger.error(f"Order monitoring loop error: {e}")
                await asyncio.sleep(5)

    async def _position_cache_update_loop(self):
        """Periodically update position cache from database"""
        while True:
            try:
                await self._update_position_cache()
                await asyncio.sleep(self.cache_update_interval)
            except Exception as e:
                logger.error(f"Position cache update error: {e}")
                await asyncio.sleep(self.cache_update_interval)

    async def _update_position_cache(self):
        """✅ FIXED: Update cached positions from database"""
        try:
            from database import get_database
            from sqlalchemy import select
            from models.trade import Trade, TradeStatus
            
            # ✅ FIXED: Use async generator correctly
            async for db in get_database():
                try:
                    # Fetch all open positions
                    result = await db.execute(
                        select(Trade).where(Trade.status == TradeStatus.EXECUTED)
                    )
                    open_trades = result.scalars().all()
                    
                    # Group by symbol
                    new_cache = {}
                    for trade in open_trades:
                        if trade.symbol not in new_cache:
                            new_cache[trade.symbol] = []
                        new_cache[trade.symbol].append(trade)
                    
                    self.cached_positions = new_cache
                    self.last_position_cache_update = datetime.now()
                    
                    total_positions = sum(len(positions) for positions in new_cache.values())
                    logger.debug(f"Position cache updated: {total_positions} positions across {len(new_cache)} symbols")
                    
                    break  # Exit the async for loop after successful execution
                except Exception as e:
                    logger.error(f"Database operation error in cache update: {e}")
                    break
                
        except Exception as e:
            logger.error(f"Failed to update position cache: {e}")

    async def _calculate_and_broadcast_position_pnl(self, symbol: str, bid: float, ask: float):
        """Calculate P&L for all positions of a symbol and broadcast updates (from USER perspective)"""
        try:
            # Get positions from cache
            positions = self.cached_positions.get(symbol, [])
            
            if not positions:
                return
            
            logger.debug(f"💰 Calculating P&L for {len(positions)} {symbol} positions")
            
            for trade in positions:
                try:
                    # Determine current price based on USER'S trade type (not execution type)
                    current_price = bid if trade.user_type.value == 'buy' else ask
                    
                    # Calculate unrealized P&L from USER'S perspective
                    if trade.user_type.value == 'buy':
                        # User bought, profits when price goes up
                        price_diff = current_price - trade.entry_price
                    else:
                        # User sold, profits when price goes down  
                        price_diff = trade.entry_price - current_price
                    
                    # Calculate P&L based on symbol specifications
                    point_value = self._get_point_value(symbol)
                    unrealized_pnl = price_diff * trade.volume * 1000 * point_value
                    
                    # Calculate pips from user's perspective
                    pips = self._calculate_pips(symbol, trade.entry_price, current_price, trade.user_type.value)
                    
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
                            "unrealized_pnl": round(unrealized_pnl, 2),
                            "price_diff": round(price_diff, 5),
                            "pips": round(pips, 1),
                            "open_time": trade.open_time.isoformat(),
                            "status": trade.status.value,
                            "timestamp": datetime.now().isoformat()
                        }
                    }
                    
                    # Broadcast to WebSocket subscribers
                    await self._notify_position_update(position_update)
                    
                except Exception as e:
                    logger.error(f"Error calculating P&L for trade {trade.id}: {e}")
                    
        except Exception as e:
            logger.error(f"Position P&L calculation error for {symbol}: {e}")

    def _get_point_value(self, symbol: str) -> float:
        """Get point value for P&L calculations"""
        if "JPY" in symbol:
            return 0.01  # 1 pip = 0.01 for JPY pairs
        elif symbol == "XAUUSD":
            return 0.1   # 1 pip = $0.10 for Gold per 0.01 move
        else:
            return 1     # 1 pip = $1 for major pairs per 0.0001 move

    def _calculate_pips(self, symbol: str, entry_price: float, current_price: float, trade_type: str) -> float:
        """Calculate pips gained/lost from user's perspective"""
        if trade_type == 'buy':
            price_diff = current_price - entry_price
        else:
            price_diff = entry_price - current_price
        
        if "JPY" in symbol:
            return price_diff * 100
        elif symbol == "XAUUSD":
            return price_diff * 10
        else:
            return price_diff * 10000

    def _reset_daily_stats(self):
        """Reset daily statistics"""
        logger.info("Resetting daily price statistics")
        for symbol in ["EURUSD", "USDJPY", "XAUUSD"]:  # Only these 3 symbols
            if symbol in self.prices:
                current_price = self.prices[symbol]
                self.daily_stats[symbol] = {
                    "open": current_price.get("bid", 0),
                    "high": current_price.get("ask", 0),
                    "low": current_price.get("bid", 0),
                    "volume": 0
                }
            else:
                self.daily_stats[symbol] = {
                    "open": 0,
                    "high": 0,
                    "low": float('inf'),
                    "volume": 0
                }

    def _update_daily_stats(self, symbol: str, bid: float, ask: float):
        """Update daily high/low statistics"""
        if symbol not in self.daily_stats:
            self.daily_stats[symbol] = {
                "open": bid,
                "high": ask,
                "low": bid,
                "volume": 0
            }
        else:
            stats = self.daily_stats[symbol]
            stats["high"] = max(stats["high"], ask)
            stats["low"] = min(stats["low"], bid)
            stats["volume"] += 1

    async def _notify_price_update(self, price_data: Dict):
        """Notify subscribers of price updates"""
        if not self.subscribers:
            return
        
        message = {
            "type": "price_update",
            "data": price_data
        }
        
        await self._broadcast_message(message)

    async def _notify_position_update(self, position_update: Dict):
        """Notify subscribers of position P&L updates"""
        if not self.subscribers:
            return
        
        await self._broadcast_message(position_update)

    async def _broadcast_message(self, message: Dict):
        """Broadcast message to all connected WebSocket clients"""
        if not self.subscribers:
            return
        
        active_subscribers = []
        message_str = json.dumps(message, default=str)
        
        for websocket in self.subscribers:
            try:
                await websocket.send_text(message_str)
                active_subscribers.append(websocket)
            except Exception as e:
                logger.debug(f"WebSocket send failed: {e}")
                pass  # WebSocket disconnected
        
        self.subscribers = active_subscribers

    async def get_price(self, symbol: str) -> Optional[Dict]:
        """Get current price for symbol"""
        if symbol in self.prices:
            return self.prices[symbol]
        
        # Fallback to MT5
        price_data = await self.mt5_service.get_symbol_price(symbol)
        if price_data:
            return {
                "symbol": symbol,
                "bid": price_data["bid"],
                "ask": price_data["ask"],
                "timestamp": datetime.now().isoformat(),
                "spread": price_data["ask"] - price_data["bid"]
            }
        
        return None

    def add_subscriber(self, websocket):
        """Add WebSocket subscriber"""
        self.subscribers.append(websocket)
        logger.info(f"WebSocket subscriber added. Total: {len(self.subscribers)}")

    def remove_subscriber(self, websocket):
        """Remove WebSocket subscriber"""
        if websocket in self.subscribers:
            self.subscribers.remove(websocket)
            logger.info(f"WebSocket subscriber removed. Total: {len(self.subscribers)}")

    async def refresh_position_cache(self):
        """Manually refresh position cache"""
        await self._update_position_cache()
        logger.info("Position cache manually refreshed")

    def get_cache_stats(self):
        """Get position cache statistics"""
        total_positions = sum(len(positions) for positions in self.cached_positions.values())
        pending_orders = len(self.trade_service.pending_limit_orders) if self.trade_service else 0
        
        return {
            "symbols": len(self.cached_positions),
            "total_positions": total_positions,
            "pending_orders": pending_orders,
            "last_update": self.last_position_cache_update.isoformat(),
            "cache_age_seconds": (datetime.now() - self.last_position_cache_update).total_seconds()
        }