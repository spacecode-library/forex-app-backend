# import MetaTrader5 as mt5
# from typing import Optional, Dict, Any
# import asyncio
# from datetime import datetime
# import logging
# from config import settings

# logger = logging.getLogger(__name__)

# class MT5Service:
#     def __init__(self):
#         self.connected = False
    
#     async def connect(self) -> bool:
#         """Connect to MT5 terminal"""
#         try:
#             if not mt5.initialize():
#                 logger.error("MT5 initialization failed")
#                 return False
#             if settings.MT5_LOGIN and settings.MT5_PASSWORD and settings.MT5_SERVER:
#                 if not mt5.login(settings.MT5_LOGIN, settings.MT5_PASSWORD, settings.MT5_SERVER):
#                     logger.info("mt5 data")
#                     logger.info(settings.MT5_LOGIN, settings.MT5_PASSWORD, settings.MT5_SERVER)
#                     logger.info("logger info")
#                     logger.error("MT5 login failed")
#                     return False
            
#             self.connected = True
#             logger.info("MT5 connected successfully")
#             return True
#         except Exception as e:
#             logger.error(f"MT5 connection error: {e}")
#             return False
    
#     async def disconnect(self):
#         """Disconnect from MT5"""
#         mt5.shutdown()
#         self.connected = False
    
#     async def place_order(self, symbol: str, order_type: str, volume: float, 
#                          price: Optional[float] = None, sl: Optional[float] = None, 
#                          tp: Optional[float] = None) -> Optional[Dict[str, Any]]:
#         """Place order on MT5"""
#         if not self.connected:
#             await self.connect()
        
#         try:
#             # Get symbol info
#             symbol_info = mt5.symbol_info(symbol)
#             if symbol_info is None:
#                 logger.error(f"Symbol {symbol} not found")
#                 return None
            
#             # Prepare request
#             request = {
#                 "action": mt5.TRADE_ACTION_DEAL,
#                 "symbol": symbol,
#                 "volume": volume,
#                 "type": mt5.ORDER_TYPE_BUY if order_type == "buy" else mt5.ORDER_TYPE_SELL,
#                 "deviation": 20,
#                 "magic": 123456,
#                 "comment": "FastAPI Trade",
#                 "type_time": mt5.ORDER_TIME_GTC,
#                 "type_filling": mt5.ORDER_FILLING_IOC,
#             }
            
#             if price:
#                 request["price"] = price
#             if sl:
#                 request["sl"] = sl
#             if tp:
#                 request["tp"] = tp
            
#             # Send order
#             result = mt5.order_send(request)
            
#             if result.retcode != mt5.TRADE_RETCODE_DONE:
#                 logger.error(f"Order failed: {result.comment}")
#                 return None
            
#             return {
#                 "ticket": str(result.order),
#                 "price": result.price,
#                 "volume": result.volume,
#                 "retcode": result.retcode,
#                 "comment": result.comment
#             }
            
#         except Exception as e:
#             logger.error(f"Order placement error: {e}")
#             return None
    
#     async def close_position(self, ticket: str, symbol: str, volume: float, 
#                            position_type: str) -> Optional[Dict[str, Any]]:
#         """Close position on MT5"""
#         if not self.connected:
#             await self.connect()
        
#         try:
#             # Reverse the position type for closing
#             close_type = mt5.ORDER_TYPE_SELL if position_type == "buy" else mt5.ORDER_TYPE_BUY
            
#             request = {
#                 "action": mt5.TRADE_ACTION_DEAL,
#                 "symbol": symbol,
#                 "volume": volume,
#                 "type": close_type,
#                 "position": int(ticket),
#                 "deviation": 20,
#                 "magic": 123456,
#                 "comment": "FastAPI Close",
#                 "type_time": mt5.ORDER_TIME_GTC,
#                 "type_filling": mt5.ORDER_FILLING_IOC,
#             }
            
#             result = mt5.order_send(request)
            
#             if result.retcode != mt5.TRADE_RETCODE_DONE:
#                 logger.error(f"Close failed: {result.comment}")
#                 return None
            
#             return {
#                 "ticket": str(result.order),
#                 "price": result.price,
#                 "volume": result.volume,
#                 "retcode": result.retcode,
#                 "comment": result.comment
#             }
            
#         except Exception as e:
#             logger.error(f"Position close error: {e}")
#             return None
    
#     async def get_symbol_price(self, symbol: str) -> Optional[Dict[str, float]]:
#         """Get current price for symbol"""
#         if not self.connected:
#             await self.connect()
        
#         try:
#             tick = mt5.symbol_info_tick(symbol)
#             if tick is None:
#                 return None
#             # print(tick)
#             return {
#                 "bid": tick.bid,
#                 "ask": tick.ask,
#                 "time": tick.time
#             }
#         except Exception as e:
#             logger.error(f"Price fetch error: {e}")
#             return None

# services/mt5_service.py - CORRECTED VERSION

import MetaTrader5 as mt5
import asyncio
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class MT5Service:
    def __init__(self):
        self.connected = False
    
    async def connect(self):
        """Connect to MetaTrader 5"""
        if not mt5.initialize():
            logger.error("MT5 initialization failed")
            return False
        
        self.connected = True
        logger.info("MT5 connected successfully")
        return True
    
    async def disconnect(self):
        """Disconnect from MetaTrader 5"""
        mt5.shutdown()
        self.connected = False
        logger.info("MT5 disconnected")
    
    async def place_order(self, symbol: str, order_type: str, volume: float, 
                         price: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """✅ FIXED: Place MARKET order only (no SL/TP parameters accepted)"""
        if not self.connected:
            await self.connect()
        
        try:
            # Check symbol availability
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                logger.error(f"Symbol {symbol} not found")
                return None
            
            # ✅ FIXED: Only send MARKET orders to MT5
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": mt5.ORDER_TYPE_BUY if order_type == "buy" else mt5.ORDER_TYPE_SELL,
                "deviation": 20,
                "magic": 123456,
                "comment": "FastAPI Market Order",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            # ✅ REMOVED: No price, sl, tp parameters - only market execution
            # We handle SL/TP on our backend, not on MT5
            
            # Send order
            result = mt5.order_send(request)
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"MT5 order failed: {result.comment}")
                return None
            
            logger.info(f"✅ MT5 market order executed: {result.order} at {result.price}")
            
            return {
                "ticket": str(result.order),
                "price": result.price,
                "volume": result.volume,
                "retcode": result.retcode,
                "comment": result.comment
            }
            
        except Exception as e:
            logger.error(f"MT5 order placement error: {e}")
            return None
    
    async def close_position(self, ticket: str, symbol: str, volume: float, 
                           position_type: str) -> Optional[Dict[str, Any]]:
        """✅ Close position on MT5 (market order for closing)"""
        if not self.connected:
            await self.connect()
        
        try:
            # Reverse the position type for closing
            close_type = mt5.ORDER_TYPE_SELL if position_type == "buy" else mt5.ORDER_TYPE_BUY
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": close_type,
                "position": int(ticket),
                "deviation": 20,
                "magic": 123456,
                "comment": "FastAPI Close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"MT5 close failed: {result.comment}")
                return None
            
            logger.info(f"✅ MT5 position closed: {ticket} at {result.price}")
            
            return {
                "ticket": str(result.order),
                "price": result.price,
                "volume": result.volume,
                "retcode": result.retcode,
                "comment": result.comment
            }
            
        except Exception as e:
            logger.error(f"MT5 position close error: {e}")
            return None
    
    async def get_symbol_price(self, symbol: str) -> Optional[Dict[str, float]]:
        """Get current price for symbol"""
        if not self.connected:
            await self.connect()
        
        try:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return None
            
            return {
                "bid": tick.bid,
                "ask": tick.ask,
                "time": tick.time,
                "volume": getattr(tick, 'volume', 0)
            }
        except Exception as e:
            logger.error(f"Price fetch error: {e}")
            return None