# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select, and_
# from typing import List, Optional
# import uuid
# from datetime import datetime
# import logging

# from models.trade import Trade, TradeStatus, TradeType
# from models.user import User
# from schemas.trade import TradeCreate, PositionResponse
# from services.mt5_service import MT5Service
# from services.price_service import PriceService

# logger = logging.getLogger(__name__)

# class TradeService:
#     def __init__(self, price_service: PriceService):
#         self.mt5_service = MT5Service()
#         self.price_service = price_service
    
#     async def place_trade(self, db: AsyncSession, user: User, trade_data: TradeCreate) -> Trade:
#         """Place a new trade"""
#         # Generate unique ticket
#         ticket = str(uuid.uuid4())[:8].upper()
        
#         # Reverse the execution type (user buys, we sell to market)
#         exec_type = TradeType.SELL if trade_data.user_type == TradeType.BUY else TradeType.BUY
        
#         # Create trade record
#         trade = Trade(
#             users_id=user.id,
#             ticket=ticket,
#             symbol=trade_data.symbol,
#             order_type=trade_data.order_type,
#             user_type=trade_data.user_type,
#             exec_type=exec_type,
#             volume=trade_data.volume,
#             stop_loss=trade_data.stop_loss,
#             take_profit=trade_data.take_profit,
#             is_fake=user.is_fake,
#             status=TradeStatus.PENDING
#         )
        
#         try:
#             if user.is_fake:
#                 # Fake execution - simulate immediately
#                 await self._execute_fake_trade(trade)
#             else:
#                 # Real execution - send to MT5
#                 await self._execute_real_trade(trade)
            
#             # Deduct margin from user balance (simplified)
#             margin_required = trade_data.volume * 1000  # Simplified margin calculation
#             user.balance -= margin_required
            
#             db.add(trade)
#             await db.commit()
#             await db.refresh(trade)
            
#             return trade
            
#         except Exception as e:
#             logger.error(f"Trade execution error: {e}")
#             trade.status = TradeStatus.CANCELLED
#             db.add(trade)
#             await db.commit()
#             raise
    
#     async def _execute_fake_trade(self, trade: Trade):
#         """Execute fake trade using current market price"""
#         price_data = await self.price_service.get_price(trade.symbol)
#         if not price_data:
#             raise Exception(f"No price data available for {trade.symbol}")
        
#         # Use bid for sell execution, ask for buy execution
#         if trade.exec_type == TradeType.SELL:
#             trade.entry_price = price_data["bid"]
#         else:
#             trade.entry_price = price_data["ask"]
        
#         trade.status = TradeStatus.EXECUTED
#         logger.info(f"Fake trade executed: {trade.ticket} at {trade.entry_price}")
    
#     async def _execute_real_trade(self, trade: Trade):
#         """Execute real trade via MT5"""
#         result = await self.mt5_service.place_order(
#             symbol=trade.symbol,
#             order_type=trade.exec_type.value,
#             volume=trade.volume,
#             sl=trade.stop_loss,
#             tp=trade.take_profit
#         )
        
#         if not result:
#             raise Exception("MT5 order execution failed")
        
#         trade.entry_price = result["price"]
#         trade.ticket = result["ticket"]
#         trade.status = TradeStatus.EXECUTED
#         logger.info(f"Real trade executed: {trade.ticket} at {trade.entry_price}")
    
#     async def close_trade(self, db: AsyncSession, trade: Trade) -> Trade:
#         """Close an open trade"""
#         if trade.status != TradeStatus.EXECUTED:
#             raise Exception("Trade is not open")
        
#         try:
#             if trade.is_fake:
#                 await self._close_fake_trade(trade)
#             else:
#                 await self._close_real_trade(trade)
            
#             # Calculate profit and update user balance
#             user_result = await db.execute(select(User).where(User.id == trade.users_id))
#             user = user_result.scalar_one()
            
#             # Add profit and release margin
#             margin_released = trade.volume * 1000
#             user.balance += margin_released + trade.profit
            
#             trade.status = TradeStatus.CLOSED
#             trade.close_time = datetime.now()
            
#             await db.commit()
#             return trade
            
#         except Exception as e:
#             logger.error(f"Trade close error: {e}")
#             raise
    
#     async def _close_fake_trade(self, trade: Trade):
#         """Close fake trade using current market price"""
#         price_data = await self.price_service.get_price(trade.symbol)
#         if not price_data:
#             raise Exception(f"No price data available for {trade.symbol}")
        
#         # Use bid for buy closing, ask for sell closing
#         if trade.exec_type == TradeType.SELL:
#             trade.exit_price = price_data["ask"]
#         else:
#             trade.exit_price = price_data["bid"]
        
#         # Calculate profit based on execution side
#         if trade.exec_type == TradeType.SELL:
#             # We sold, profit when price goes down
#             price_diff = trade.entry_price - trade.exit_price
#         else:
#             # We bought, profit when price goes up
#             price_diff = trade.exit_price - trade.entry_price
        
#         trade.profit = price_diff * trade.volume * 1000  # Simplified P/L calculation
    
#     async def _close_real_trade(self, trade: Trade):
#         """Close real trade via MT5"""
#         result = await self.mt5_service.close_position(
#             ticket=trade.ticket,
#             symbol=trade.symbol,
#             volume=trade.volume,
#             position_type=trade.exec_type.value
#         )
        
#         if not result:
#             raise Exception("MT5 position close failed")
        
#         trade.exit_price = result["price"]
        
#         # Calculate profit (similar to fake trade)
#         if trade.exec_type == TradeType.SELL:
#             price_diff = trade.entry_price - trade.exit_price
#         else:
#             price_diff = trade.exit_price - trade.entry_price
        
#         trade.profit = price_diff * trade.volume * 1000
    
#     async def get_open_positions(self, db: AsyncSession, user_id: str) -> List[PositionResponse]:
#         """Get all open positions for a user"""
#         result = await db.execute(
#             select(Trade).where(
#                 and_(
#                     Trade.users_id == user_id,
#                     Trade.status == TradeStatus.EXECUTED
#                 )
#             )
#         )
#         trades = result.scalars().all()
        
#         positions = []
#         for trade in trades:
#             # Get current price for unrealized P/L
#             price_data = await self.price_service.get_price(trade.symbol)
#             if price_data:
#                 current_price = price_data["bid"] if trade.exec_type == TradeType.SELL else price_data["ask"]
                
#                 # Calculate unrealized P/L
#                 if trade.exec_type == TradeType.SELL:
#                     unrealized_pnl = (trade.entry_price - current_price) * trade.volume * 1000
#                 else:
#                     unrealized_pnl = (current_price - trade.entry_price) * trade.volume * 1000
                
#                 positions.append(PositionResponse(
#                     id=trade.id,
#                     symbol=trade.symbol,
#                     user_type=trade.user_type,
#                     volume=trade.volume,
#                     entry_price=trade.entry_price,
#                     current_price=current_price,
#                     unrealized_pnl=unrealized_pnl,
#                     open_time=trade.open_time,
#                     status='EXECUTED' 
#                 ))
        
#         return positions


# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select, and_
# from typing import List, Optional
# import uuid
# from datetime import datetime
# import logging

# from models.trade import Trade, TradeStatus, TradeType
# from models.user import User
# from schemas.trade import TradeCreate, PositionResponse
# from services.mt5_service import MT5Service
# from services.price_service import PriceService

# logger = logging.getLogger(__name__)

# class TradeService:
#     def __init__(self, price_service: PriceService):
#         self.mt5_service = MT5Service()
#         self.price_service = price_service
    
#     async def place_trade(self, db: AsyncSession, user: User, trade_data: TradeCreate) -> Trade:
#         """Place a new trade"""
#         # Generate unique ticket
#         ticket = str(uuid.uuid4())[:8].upper()
        
#         # Reverse the execution type (user buys, we sell to market)
#         exec_type = TradeType.SELL if trade_data.user_type == TradeType.BUY else TradeType.BUY
        
#         # Create trade record
#         trade = Trade(
#             users_id=user.id,
#             ticket=ticket,
#             symbol=trade_data.symbol,
#             order_type=trade_data.order_type,
#             user_type=trade_data.user_type,
#             exec_type=exec_type,
#             volume=trade_data.volume,
#             stop_loss=trade_data.stop_loss,
#             take_profit=trade_data.take_profit,
#             is_fake=user.is_fake,
#             status=TradeStatus.PENDING
#         )
        
#         try:
#             if user.is_fake:
#                 # Fake execution - simulate immediately
#                 await self._execute_fake_trade(trade)
#             else:
#                 # Real execution - send to MT5
#                 await self._execute_real_trade(trade)
            
#             # Deduct margin from user balance (simplified)
#             margin_required = trade_data.volume * 1000  # Simplified margin calculation
#             user.balance -= margin_required
            
#             db.add(trade)
#             await db.commit()
#             await db.refresh(trade)
            
#             return trade
            
#         except Exception as e:
#             logger.error(f"Trade execution error: {e}")
#             trade.status = TradeStatus.CANCELLED
#             db.add(trade)
#             await db.commit()
#             raise
    
#     async def _execute_fake_trade(self, trade: Trade):
#         """Execute fake trade using current market price"""
#         price_data = await self.price_service.get_price(trade.symbol)
#         if not price_data:
#             raise Exception(f"No price data available for {trade.symbol}")
        
#         # Use bid for sell execution, ask for buy execution
#         if trade.exec_type == TradeType.SELL:
#             trade.entry_price = price_data["bid"]
#         else:
#             trade.entry_price = price_data["ask"]
        
#         trade.status = TradeStatus.EXECUTED
#         logger.info(f"Fake trade executed: {trade.ticket} at {trade.entry_price}")
    
#     async def _execute_real_trade(self, trade: Trade):
#         """Execute real trade via MT5"""
#         result = await self.mt5_service.place_order(
#             symbol=trade.symbol,
#             order_type=trade.exec_type.value,
#             volume=trade.volume,
#             sl=trade.stop_loss,
#             tp=trade.take_profit
#         )
        
#         if not result:
#             raise Exception("MT5 order execution failed")
        
#         trade.entry_price = result["price"]
#         trade.ticket = result["ticket"]
#         trade.status = TradeStatus.EXECUTED
#         logger.info(f"Real trade executed: {trade.ticket} at {trade.entry_price}")
    
#     async def close_trade(self, db: AsyncSession, trade: Trade) -> Trade:
#         """Close an open trade"""
#         if trade.status != TradeStatus.EXECUTED:
#             raise Exception("Trade is not open")
        
#         try:
#             if trade.is_fake:
#                 await self._close_fake_trade(trade)
#             else:
#                 await self._close_real_trade(trade)
            
#             # Calculate profit and update user balance
#             user_result = await db.execute(select(User).where(User.id == trade.users_id))
#             user = user_result.scalar_one()
            
#             # Add profit and release margin
#             margin_released = trade.volume * 1000
#             user.balance += margin_released + trade.profit
            
#             trade.status = TradeStatus.CLOSED
#             trade.close_time = datetime.now()
            
#             await db.commit()
#             return trade
            
#         except Exception as e:
#             logger.error(f"Trade close error: {e}")
#             raise
    
#     async def _close_fake_trade(self, trade: Trade):
#         """Close fake trade using current market price"""
#         price_data = await self.price_service.get_price(trade.symbol)
#         if not price_data:
#             raise Exception(f"No price data available for {trade.symbol}")
        
#         # Use bid for buy closing, ask for sell closing
#         if trade.exec_type == TradeType.SELL:
#             trade.exit_price = price_data["ask"]
#         else:
#             trade.exit_price = price_data["bid"]
        
#         # Calculate profit based on execution side
#         if trade.exec_type == TradeType.SELL:
#             # We sold, profit when price goes down
#             price_diff = trade.entry_price - trade.exit_price
#         else:
#             # We bought, profit when price goes up
#             price_diff = trade.exit_price - trade.entry_price
        
#         trade.profit = price_diff * trade.volume * 1000  # Simplified P/L calculation
    
#     async def _close_real_trade(self, trade: Trade):
#         """Close real trade via MT5"""
#         result = await self.mt5_service.close_position(
#             ticket=trade.ticket,
#             symbol=trade.symbol,
#             volume=trade.volume,
#             position_type=trade.exec_type.value
#         )
        
#         if not result:
#             raise Exception("MT5 position close failed")
        
#         trade.exit_price = result["price"]
        
#         # Calculate profit (similar to fake trade)
#         if trade.exec_type == TradeType.SELL:
#             price_diff = trade.entry_price - trade.exit_price
#         else:
#             price_diff = trade.exit_price - trade.entry_price
        
#         trade.profit = price_diff * trade.volume * 1000
    
#     async def get_open_positions(self, db: AsyncSession, user_id: str) -> List[PositionResponse]:
#         """Get all open positions for a user"""
#         result = await db.execute(
#             select(Trade).where(
#                 and_(
#                     Trade.users_id == user_id,
#                     Trade.status == TradeStatus.EXECUTED
#                 )
#             )
#         )
#         trades = result.scalars().all()
        
#         positions = []
#         for trade in trades:
#             # Get current price for unrealized P/L
#             price_data = await self.price_service.get_price(trade.symbol)
#             if price_data:
#                 current_price = price_data["bid"] if trade.exec_type == TradeType.SELL else price_data["ask"]
                
#                 # Calculate unrealized P/L
#                 if trade.exec_type == TradeType.SELL:
#                     unrealized_pnl = (trade.entry_price - current_price) * trade.volume * 1000
#                 else:
#                     unrealized_pnl = (current_price - trade.entry_price) * trade.volume * 1000
                
#                 positions.append(PositionResponse(
#                     id=trade.id,
#                     symbol=trade.symbol,
#                     user_type=trade.user_type,
#                     volume=trade.volume,
#                     entry_price=trade.entry_price,
#                     current_price=current_price,
#                     unrealized_pnl=unrealized_pnl,
#                     open_time=trade.open_time,
#                     status='EXECUTED' 
#                 ))
        
# #         return positions
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select, and_, or_
# from typing import List, Optional, Dict
# import uuid
# from datetime import datetime
# import logging

# from models.trade import Trade, TradeStatus, TradeType, OrderType
# from models.user import User
# from schemas.trade import TradeCreate, PositionResponse
# from services.mt5_service import MT5Service
# from services.price_service import PriceService

# logger = logging.getLogger(__name__)

# class TradeService:
#     def __init__(self, price_service: PriceService):
#         self.mt5_service = MT5Service()
#         self.price_service = price_service
#         self.pending_limit_orders: Dict[str, Trade] = {}  # Store pending limit orders
#         self.commission_per_lot = 3.0  # $3 commission per lot
    
#     async def place_trade(self, db: AsyncSession, user: User, trade_data: TradeCreate) -> Trade:
#         """Place a new trade with limit order and commission support"""
#         # Generate unique ticket
#         ticket = str(uuid.uuid4())[:8].upper()
        
#         # Reverse the execution type (user buys, we sell to market)
#         exec_type = TradeType.SELL if trade_data.user_type == TradeType.BUY else TradeType.BUY
        
#         # Calculate commission
#         commission = trade_data.volume * self.commission_per_lot
        
#         # Create trade record
#         trade = Trade(
#             users_id=user.id,
#             ticket=ticket,
#             symbol=trade_data.symbol,
#             order_type=trade_data.order_type,
#             user_type=trade_data.user_type,
#             exec_type=exec_type,
#             volume=trade_data.volume,
#             stop_loss=trade_data.stop_loss,
#             take_profit=trade_data.take_profit,
#             is_fake=user.is_fake,
#             status=TradeStatus.PENDING
#         )
        
#         try:
#             if trade_data.order_type == OrderType.MARKET:
#                 # Execute market order immediately
#                 await self._execute_trade_immediately(trade, user, db, commission)
#             else:
#                 # Handle limit order - store for monitoring
#                 if not trade_data.price:
#                     raise Exception("Limit orders require a price")
                
#                 trade.entry_price = trade_data.price  # Store target price
#                 await self._validate_and_store_limit_order(trade, user, db, commission)
            
#             db.add(trade)
#             await db.commit()
#             await db.refresh(trade)
            
#             return trade
            
#         except Exception as e:
#             logger.error(f"Trade execution error: {e}")
#             trade.status = TradeStatus.CANCELLED
#             db.add(trade)
#             await db.commit()
#             raise
    
#     async def _execute_trade_immediately(self, trade: Trade, user: User, db: AsyncSession, commission: float):
#         """Execute market order immediately"""
#         try:
#             if user.is_fake:
#                 await self._execute_fake_trade(trade)
#             else:
#                 await self._execute_real_trade(trade)
            
#             # Deduct margin + commission from user balance
#             margin_required = trade.volume * 1000  # Simplified margin calculation
#             total_deduction = margin_required + commission
            
#             if user.balance < total_deduction:
#                 raise Exception(f"Insufficient balance. Required: ${total_deduction:.2f}, Available: ${user.balance:.2f}")
            
#             user.balance -= total_deduction
#             trade.status = TradeStatus.EXECUTED
            
#             logger.info(f"Market order executed: {trade.ticket}, Commission: ${commission}")
            
#         except Exception as e:
#             logger.error(f"Market order execution failed: {e}")
#             trade.status = TradeStatus.CANCELLED
#             raise
    
#     async def _validate_and_store_limit_order(self, trade: Trade, user: User, db: AsyncSession, commission: float):
#         """Validate and store limit order for monitoring (NOT sent to MT5)"""
#         # Get current price for validation
#         current_price = await self.price_service.get_price(trade.symbol)
#         if not current_price:
#             raise Exception(f"No price data available for {trade.symbol}")
        
#         target_price = trade.entry_price
#         current_market_price = current_price["ask"] if trade.user_type == TradeType.BUY else current_price["bid"]
        
#         # Validate limit order logic
#         if trade.user_type == TradeType.BUY and target_price >= current_market_price:
#             raise Exception("Buy limit order must be below current market price")
#         elif trade.user_type == TradeType.SELL and target_price <= current_market_price:
#             raise Exception("Sell limit order must be above current market price")
        
#         # Check if user has sufficient balance for when order executes
#         margin_required = trade.volume * 1000
#         total_required = margin_required + commission
        
#         if user.balance < total_required:
#             raise Exception(f"Insufficient balance for order. Required: ${total_required:.2f}")
        
#         # Store pending order for monitoring (NO MT5 EXECUTION YET)
#         self.pending_limit_orders[trade.ticket] = trade
#         trade.status = TradeStatus.PENDING
        
#         logger.info(f"Limit order stored locally: {trade.ticket} - {trade.user_type} {trade.symbol} at {target_price} (will execute on our backend when price reached)")
    
#     async def monitor_pending_orders(self, db: AsyncSession):
#         """Monitor pending limit orders for execution"""
#         if not self.pending_limit_orders:
#             return
        
#         executed_orders = []
        
#         for ticket, trade in self.pending_limit_orders.items():
#             try:
#                 current_price = await self.price_service.get_price(trade.symbol)
#                 if not current_price:
#                     continue
                
#                 target_price = trade.entry_price
#                 current_market_price = current_price["ask"] if trade.user_type == TradeType.BUY else current_price["bid"]
                
#                 # Check if limit order should execute
#                 should_execute = False
                
#                 if trade.user_type == TradeType.BUY and current_market_price <= target_price:
#                     should_execute = True
#                 elif trade.user_type == TradeType.SELL and current_market_price >= target_price:
#                     should_execute = True
                
#                 if should_execute:
#                     logger.info(f"LIMIT ORDER TRIGGERED: {ticket} - executing locally on our backend")
                    
#                     # Get fresh user data
#                     user_result = await db.execute(select(User).where(User.id == trade.users_id))
#                     user = user_result.scalar_one()
                    
#                     # Execute the trade locally (will go to MT5 as market order)
#                     commission = trade.volume * self.commission_per_lot
#                     await self._execute_trade_immediately(trade, user, db, commission)
                    
#                     # Update database
#                     await db.commit()
                    
#                     executed_orders.append(ticket)
                    
#                     logger.info(f"LIMIT ORDER EXECUTED: {ticket} - now executed as market order on MT5")
                    
#             except Exception as e:
#                 logger.error(f"Error executing limit order {ticket}: {e}")
#                 trade.status = TradeStatus.CANCELLED
#                 executed_orders.append(ticket)
        
#         # Remove executed/cancelled orders from pending
#         for ticket in executed_orders:
#             self.pending_limit_orders.pop(ticket, None)
    
#     async def monitor_stop_loss_take_profit(self, db: AsyncSession):
#         """Monitor open positions for SL/TP triggers"""
#         try:
#             # Get all open positions with SL or TP set
#             result = await db.execute(
#                 select(Trade).where(
#                     and_(
#                         Trade.status == TradeStatus.EXECUTED,
#                         or_(
#                             Trade.stop_loss.isnot(None),
#                             Trade.take_profit.isnot(None)
#                         )
#                     )
#                 )
#             )
#             open_trades = result.scalars().all()
            
#             for trade in open_trades:
#                 try:
#                     current_price = await self.price_service.get_price(trade.symbol)
#                     if not current_price:
#                         continue
                    
#                     # Get current price relevant to user's position
#                     current_market_price = current_price["bid"] if trade.user_type == TradeType.BUY else current_price["ask"]
                    
#                     should_close = False
#                     close_reason = ""
                    
#                     # Check Stop Loss
#                     if trade.stop_loss:
#                         if trade.user_type == TradeType.BUY and current_market_price <= trade.stop_loss:
#                             should_close = True
#                             close_reason = "Stop Loss"
#                         elif trade.user_type == TradeType.SELL and current_market_price >= trade.stop_loss:
#                             should_close = True
#                             close_reason = "Stop Loss"
                    
#                     # Check Take Profit
#                     if trade.take_profit:
#                         if trade.user_type == TradeType.BUY and current_market_price >= trade.take_profit:
#                             should_close = True
#                             close_reason = "Take Profit"
#                         elif trade.user_type == TradeType.SELL and current_market_price <= trade.take_profit:
#                             should_close = True
#                             close_reason = "Take Profit"
                    
#                     if should_close:
#                         logger.info(f"Auto-closing position {trade.ticket} due to {close_reason}")
#                         await self.close_trade(db, trade, auto_close=True, close_reason=close_reason)
                        
#                 except Exception as e:
#                     logger.error(f"Error monitoring SL/TP for trade {trade.ticket}: {e}")
                    
#         except Exception as e:
#             logger.error(f"SL/TP monitoring error: {e}")
    
#     async def _execute_fake_trade(self, trade: Trade):
#         """Execute fake trade using current market price"""
#         price_data = await self.price_service.get_price(trade.symbol)
#         if not price_data:
#             raise Exception(f"No price data available for {trade.symbol}")
        
#         # Use appropriate price based on user action (not execution side)
#         if trade.user_type == TradeType.BUY:
#             trade.entry_price = price_data["ask"]  # User buys at ask
#         else:
#             trade.entry_price = price_data["bid"]  # User sells at bid
        
#         logger.info(f"Fake trade executed: {trade.ticket} at {trade.entry_price}")
    
#     async def _execute_real_trade(self, trade: Trade):
#         """Execute real trade via MT5 (NO SL/TP sent to MT5 - we handle internally)"""
#         result = await self.mt5_service.place_order(
#             symbol=trade.symbol,
#             order_type=trade.exec_type.value,  # Use reversed execution type for MT5
#             volume=trade.volume
#             # NO sl=trade.stop_loss, tp=trade.take_profit - we handle SL/TP on our side
#         )
        
#         if not result:
#             raise Exception("MT5 order execution failed")
        
#         trade.entry_price = result["price"]
#         trade.ticket = result["ticket"]
#         logger.info(f"Real trade executed: {trade.ticket} at {trade.entry_price} (SL/TP managed internally)")
    
#     async def close_trade(self, db: AsyncSession, trade: Trade, auto_close: bool = False, close_reason: str = "Manual") -> Trade:
#         """Close an open trade with commission deduction"""
#         if trade.status != TradeStatus.EXECUTED:
#             raise Exception("Trade is not open")
        
#         logger.info(f"🔄 CLOSING TRADE DEBUG - Starting close for {trade.ticket}")
#         logger.info(f"📊 Before close - Entry Price: {trade.entry_price}, User Type: {trade.user_type}, Volume: {trade.volume}")
        
#         try:
#             if trade.is_fake:
#                 await self._close_fake_trade(trade)
#             else:
#                 await self._close_real_trade(trade)
            
#             logger.info(f"📊 After close - Exit Price: {trade.exit_price}")
            
#             # Calculate commission for closing (only closing commission, opening already deducted)
#             closing_commission = trade.volume * self.commission_per_lot
#             logger.info(f"💰 Closing Commission: ${closing_commission}")
            
#             # Get user and update balance
#             user_result = await db.execute(select(User).where(User.id == trade.users_id))
#             user = user_result.scalar_one()
            
#             # Calculate P&L from user's perspective (same logic as real-time display)
#             user_pnl = self._calculate_user_pnl(trade)
#             logger.info(f"📈 Calculated User P&L (GROSS): ${user_pnl}")
            
#             # IMPORTANT: Store the NET profit (after closing commission) in trade.profit
#             trade.profit = user_pnl - closing_commission
#             logger.info(f"💵 Final NET Profit (after closing commission): ${trade.profit}")
            
#             # Release margin and add net profit to balance
#             margin_released = trade.volume * 1000
#             user_balance_before = user.balance
#             user.balance += margin_released + trade.profit
            
#             logger.info(f"💳 Balance Update - Before: ${user_balance_before}, Margin Released: ${margin_released}, Net Profit: ${trade.profit}, After: ${user.balance}")
            
#             trade.status = TradeStatus.CLOSED
#             trade.close_time = datetime.now()
            
#             await db.commit()
            
#             logger.info(f"✅ Trade closed successfully: {trade.ticket}")
#             logger.info(f"📋 FINAL SUMMARY - Gross P&L: ${user_pnl:.2f}, Closing Commission: ${closing_commission:.2f}, Net P&L: ${trade.profit:.2f}")
#             return trade
            
#         except Exception as e:
#             logger.error(f"❌ Trade close error: {e}")
#             raise
    
#     def _calculate_user_pnl(self, trade: Trade) -> float:
#         """Calculate P&L from user's perspective (not execution side)"""
#         logger.info(f"🧮 P&L CALCULATION DEBUG for {trade.ticket}:")
#         logger.info(f"   Entry Price: {trade.entry_price}")
#         logger.info(f"   Exit Price: {trade.exit_price}")
#         logger.info(f"   User Type: {trade.user_type}")
#         logger.info(f"   Volume: {trade.volume}")
#         logger.info(f"   Symbol: {trade.symbol}")
        
#         if not trade.entry_price or not trade.exit_price:
#             logger.warning(f"⚠️  Missing prices! Entry: {trade.entry_price}, Exit: {trade.exit_price}")
#             return 0.0
        
#         # Calculate based on what the USER did (buy/sell), not the execution side
#         if trade.user_type == TradeType.BUY:
#             # User bought, profits when price goes up
#             price_diff = trade.exit_price - trade.entry_price
#             logger.info(f"   📈 BUY trade: {trade.exit_price} - {trade.entry_price} = {price_diff}")
#         else:
#             # User sold, profits when price goes down
#             price_diff = trade.entry_price - trade.exit_price
#             logger.info(f"   📉 SELL trade: {trade.entry_price} - {trade.exit_price} = {price_diff}")
        
#         # Apply point value based on symbol
#         point_value = self._get_point_value(trade.symbol)
#         logger.info(f"   🔢 Point value for {trade.symbol}: {point_value}")
        
#         pnl = price_diff * trade.volume * 1000 * point_value
#         logger.info(f"   💰 Final calculation: {price_diff} * {trade.volume} * 1000 * {point_value} = ${pnl}")
        
#         return pnl
    
#     def _get_point_value(self, symbol: str) -> float:
#         """Get point value for P&L calculations"""
#         if "JPY" in symbol:
#             return 0.01  # 1 pip = 0.01 for JPY pairs
#         elif symbol == "XAUUSD":
#             return 0.1   # 1 pip = $0.10 for Gold per 0.01 move
#         else:
#             return 1     # 1 pip = $1 for major pairs per 0.0001 move
    
#     async def _close_fake_trade(self, trade: Trade):
#         """Close fake trade using current market price"""
#         logger.info(f"🎭 FAKE TRADE CLOSE DEBUG for {trade.ticket}")
        
#         price_data = await self.price_service.get_price(trade.symbol)
#         if not price_data:
#             logger.error(f"❌ No price data available for {trade.symbol}")
#             raise Exception(f"No price data available for {trade.symbol}")
        
#         logger.info(f"📊 Current market prices - Bid: {price_data['bid']}, Ask: {price_data['ask']}")
        
#         # Use appropriate closing price based on user's position
#         if trade.user_type == TradeType.BUY:
#             trade.exit_price = price_data["bid"]  # User sells at bid
#             logger.info(f"📈 User had BUY position, closing at BID: {trade.exit_price}")
#         else:
#             trade.exit_price = price_data["ask"]  # User covers at ask
#             logger.info(f"📉 User had SELL position, closing at ASK: {trade.exit_price}")
        
#         logger.info(f"✅ Exit price set to: {trade.exit_price}")
    
#     async def _close_real_trade(self, trade: Trade):
#         """Close real trade via MT5 (no SL/TP parameters)"""
#         logger.info(f"🏦 REAL TRADE CLOSE DEBUG for {trade.ticket}")
        
#         result = await self.mt5_service.close_position(
#             ticket=trade.ticket,
#             symbol=trade.symbol,
#             volume=trade.volume,
#             position_type=trade.exec_type.value  # Use execution type for MT5
#             # No SL/TP parameters - we handle everything on our side
#         )
        
#         if not result:
#             logger.error(f"❌ MT5 position close failed for {trade.ticket}")
#             raise Exception("MT5 position close failed")
        
#         logger.info(f"🏦 MT5 close result: {result}")
#         trade.exit_price = result["price"]
#         logger.info(f"✅ Exit price from MT5: {trade.exit_price}")
    
#     async def get_open_positions(self, db: AsyncSession, user_id: str) -> List[PositionResponse]:
#         """Get all open positions for a user with correct P&L calculation"""
#         result = await db.execute(
#             select(Trade).where(
#                 and_(
#                     Trade.users_id == user_id,
#                     Trade.status == TradeStatus.EXECUTED
#                 )
#             )
#         )
#         trades = result.scalars().all()
        
#         positions = []
#         for trade in trades:
#             # Get current price for unrealized P/L
#             price_data = await self.price_service.get_price(trade.symbol)
#             if price_data:
#                 # Current price from user's perspective (not execution side)
#                 current_price = price_data["bid"] if trade.user_type == TradeType.BUY else price_data["ask"]
                
#                 # Calculate unrealized P&L from user's perspective
#                 if trade.user_type == TradeType.BUY:
#                     # User bought, profits when price goes up
#                     price_diff = current_price - trade.entry_price
#                 else:
#                     # User sold, profits when price goes down
#                     price_diff = trade.entry_price - current_price
                
#                 point_value = self._get_point_value(trade.symbol)
#                 unrealized_pnl = price_diff * trade.volume * 1000 * point_value
                
#                 positions.append(PositionResponse(
#                     id=trade.id,
#                     symbol=trade.symbol,
#                     user_type=trade.user_type,
#                     volume=trade.volume,
#                     entry_price=trade.entry_price,
#                     current_price=current_price,
#                     unrealized_pnl=unrealized_pnl,
#                     open_time=trade.open_time,
#                     status='EXECUTED' 
#                 ))
        
#         return positions


# services/trade_service.py - CORRECTED VERSION
# services/trade_service.py - CORRECTED VERSION

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from typing import List, Optional, Dict
import uuid
from datetime import datetime
import logging

from models.trade import Trade, TradeStatus, TradeType, OrderType
from models.user import User
from schemas.trade import TradeCreate, PositionResponse
from services.mt5_service import MT5Service
from services.price_service import PriceService

logger = logging.getLogger(__name__)

class TradeService:
    def __init__(self, price_service: PriceService):
        self.mt5_service = MT5Service()
        self.price_service = price_service
        self.pending_limit_orders: Dict[str, Trade] = {}  # Store pending limit orders
        self.commission_per_lot = 6.0  # $6 commission per lot
    
    async def place_trade(self, db: AsyncSession, user: User, trade_data: TradeCreate) -> Trade:
        """Place a new trade with correct limit order and commission support"""
        # Generate unique ticket
        ticket = str(uuid.uuid4())[:8].upper()
        
        # Reverse the execution type (user buys, we sell to market)
        exec_type = TradeType.SELL if trade_data.user_type == TradeType.BUY else TradeType.BUY
        
        # Calculate commission
        commission = trade_data.volume * self.commission_per_lot
        
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
            if trade_data.order_type == OrderType.MARKET:
                # ✅ FIXED: Execute market order immediately
                await self._execute_trade_immediately(trade, user, db, commission)
            else:
                # ✅ FIXED: Handle limit order - store for monitoring (DON'T execute yet)
                if not trade_data.price:
                    raise Exception("Limit orders require a price")
                
                trade.entry_price = trade_data.price  # Store target price
                await self._validate_and_store_limit_order(trade, user, db, commission)
            
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
    
    async def _execute_trade_immediately(self, trade: Trade, user: User, db: AsyncSession, commission: float):
        """Execute market order immediately"""
        try:
            if user.is_fake:
                await self._execute_fake_trade(trade)
            else:
                # ✅ FIXED: For real users, send ONLY market order to MT5 (no SL/TP)
                await self._execute_real_trade(trade)
            
            # Deduct margin + commission from user balance
            margin_required = trade.volume * 1000  # Simplified margin calculation
            total_deduction = margin_required + commission
            
            if user.balance < total_deduction:
                raise Exception(f"Insufficient balance. Required: ${total_deduction:.2f}, Available: ${user.balance:.2f}")
            
            user.balance -= total_deduction
            trade.status = TradeStatus.EXECUTED
            
            logger.info(f"Market order executed: {trade.ticket}, Commission: ${commission}")
            
        except Exception as e:
            logger.error(f"Market order execution failed: {e}")
            trade.status = TradeStatus.CANCELLED
            raise
    
    async def _validate_and_store_limit_order(self, trade: Trade, user: User, db: AsyncSession, commission: float):
        """✅ FIXED: Validate and store limit order for monitoring (NOT sent to MT5)"""
        # Get current price for validation
        current_price = await self.price_service.get_price(trade.symbol)
        if not current_price:
            raise Exception(f"No price data available for {trade.symbol}")
        
        target_price = trade.entry_price
        current_market_price = current_price["ask"] if trade.user_type == TradeType.BUY else current_price["bid"]
        
        # Validate limit order logic
        if trade.user_type == TradeType.BUY and target_price >= current_market_price:
            raise Exception("Buy limit order must be below current market price")
        elif trade.user_type == TradeType.SELL and target_price <= current_market_price:
            raise Exception("Sell limit order must be above current market price")
        
        # Check if user has sufficient balance for when order executes
        margin_required = trade.volume * 1000
        total_required = margin_required + commission
        
        if user.balance < total_required:
            raise Exception(f"Insufficient balance for order. Required: ${total_required:.2f}")
        
        # ✅ Store pending order for monitoring (NO MT5 EXECUTION YET)
        self.pending_limit_orders[trade.ticket] = trade
        trade.status = TradeStatus.PENDING
        
        logger.info(f"Limit order stored locally: {trade.ticket} - {trade.user_type} {trade.symbol} at {target_price} (will execute on our backend when price reached)")
    
    async def monitor_pending_orders(self, db: AsyncSession):
        """✅ Monitor pending limit orders for execution"""
        if not self.pending_limit_orders:
            return
        
        executed_orders = []
        
        for ticket, trade in self.pending_limit_orders.items():
            try:
                current_price = await self.price_service.get_price(trade.symbol)
                if not current_price:
                    continue
                
                target_price = trade.entry_price
                current_market_price = current_price["ask"] if trade.user_type == TradeType.BUY else current_price["bid"]
                
                # Check if limit order should execute
                should_execute = False
                
                if trade.user_type == TradeType.BUY and current_market_price <= target_price:
                    should_execute = True
                elif trade.user_type == TradeType.SELL and current_market_price >= target_price:
                    should_execute = True
                
                if should_execute:
                    logger.info(f"LIMIT ORDER TRIGGERED: {ticket} - executing as market order")
                    
                    # Get fresh user data
                    user_result = await db.execute(select(User).where(User.id == trade.users_id))
                    user = user_result.scalar_one()
                    
                    # ✅ Execute the trade immediately (will go to MT5 as market order for real users)
                    commission = trade.volume * self.commission_per_lot
                    await self._execute_trade_immediately(trade, user, db, commission)
                    
                    # Update database
                    await db.commit()
                    
                    executed_orders.append(ticket)
                    
                    logger.info(f"LIMIT ORDER EXECUTED: {ticket} - now executed as market order")
                    
            except Exception as e:
                logger.error(f"Error executing limit order {ticket}: {e}")
                trade.status = TradeStatus.CANCELLED
                executed_orders.append(ticket)
        
        # Remove executed/cancelled orders from pending
        for ticket in executed_orders:
            self.pending_limit_orders.pop(ticket, None)
    
    async def monitor_stop_loss_take_profit(self, db: AsyncSession):
        """✅ Monitor open positions for SL/TP triggers"""
        try:
            # Get all open positions with SL or TP set
            result = await db.execute(
                select(Trade).where(
                    and_(
                        Trade.status == TradeStatus.EXECUTED,
                        or_(
                            Trade.stop_loss.isnot(None),
                            Trade.take_profit.isnot(None)
                        )
                    )
                )
            )
            open_trades = result.scalars().all()
            
            for trade in open_trades:
                try:
                    current_price = await self.price_service.get_price(trade.symbol)
                    if not current_price:
                        continue
                    
                    # ✅ FIXED: Get current price relevant to user's position (not execution side)
                    current_market_price = current_price["bid"] if trade.user_type == TradeType.BUY else current_price["ask"]
                    
                    should_close = False
                    close_reason = ""
                    
                    # ✅ Check Stop Loss from USER perspective
                    if trade.stop_loss:
                        if trade.user_type == TradeType.BUY and current_market_price <= trade.stop_loss:
                            should_close = True
                            close_reason = "Stop Loss"
                        elif trade.user_type == TradeType.SELL and current_market_price >= trade.stop_loss:
                            should_close = True
                            close_reason = "Stop Loss"
                    
                    # ✅ Check Take Profit from USER perspective
                    if trade.take_profit:
                        if trade.user_type == TradeType.BUY and current_market_price >= trade.take_profit:
                            should_close = True
                            close_reason = "Take Profit"
                        elif trade.user_type == TradeType.SELL and current_market_price <= trade.take_profit:
                            should_close = True
                            close_reason = "Take Profit"
                    
                    if should_close:
                        logger.info(f"Auto-closing position {trade.ticket} due to {close_reason}")
                        await self.close_trade(db, trade, auto_close=True, close_reason=close_reason)
                        
                except Exception as e:
                    logger.error(f"Error monitoring SL/TP for trade {trade.ticket}: {e}")
                    
        except Exception as e:
            logger.error(f"SL/TP monitoring error: {e}")
    
    async def _execute_fake_trade(self, trade: Trade):
        """Execute fake trade using current market price"""
        price_data = await self.price_service.get_price(trade.symbol)
        if not price_data:
            raise Exception(f"No price data available for {trade.symbol}")
        
        # ✅ FIXED: Use appropriate price based on user action (not execution side)
        if trade.user_type == TradeType.BUY:
            trade.entry_price = price_data["ask"]  # User buys at ask
        else:
            trade.entry_price = price_data["bid"]  # User sells at bid
        
        logger.info(f"Fake trade executed: {trade.ticket} at {trade.entry_price}")
    
    async def _execute_real_trade(self, trade: Trade):
        """✅ FIXED: Execute real trade via MT5 (NO SL/TP sent to MT5)"""
        result = await self.mt5_service.place_order(
            symbol=trade.symbol,
            order_type=trade.exec_type.value,  # Use reversed execution type for MT5
            volume=trade.volume
            # ✅ REMOVED: sl=trade.stop_loss, tp=trade.take_profit - we handle SL/TP internally
        )
        
        if not result:
            raise Exception("MT5 order execution failed")
        
        trade.entry_price = result["price"]
        trade.ticket = result["ticket"]
        logger.info(f"Real trade executed: {trade.ticket} at {trade.entry_price} (SL/TP managed internally)")
    
    async def close_trade(self, db: AsyncSession, trade: Trade, auto_close: bool = False, close_reason: str = "Manual") -> Trade:
        """✅ Close an open trade"""
        if trade.status != TradeStatus.EXECUTED:
            raise Exception("Trade is not open")
        
        try:
            if trade.is_fake:
                await self._close_fake_trade(trade)
            else:
                # ✅ For real users, close position on MT5
                await self._close_real_trade(trade)
            
            # Calculate commission for closing
            closing_commission = trade.volume * self.commission_per_lot
            
            # Get user and update balance
            user_result = await db.execute(select(User).where(User.id == trade.users_id))
            user = user_result.scalar_one()
            
            # ✅ FIXED: Calculate P&L from user's perspective
            user_pnl = self._calculate_user_pnl(trade)
            
            # Store the NET profit (after closing commission)
            trade.profit = user_pnl - closing_commission
            
            # Release margin and add net profit to balance
            margin_released = trade.volume * 1000
            user.balance += margin_released + trade.profit
            
            trade.status = TradeStatus.CLOSED
            trade.close_time = datetime.now()
            
            await db.commit()
            
            logger.info(f"Trade closed: {trade.ticket}, Net P&L: ${trade.profit:.2f}")
            return trade
            
        except Exception as e:
            logger.error(f"Trade close error: {e}")
            raise
    
    def _calculate_user_pnl(self, trade: Trade) -> float:
        """✅ FIXED: Calculate P&L from user's perspective"""
        if not trade.entry_price or not trade.exit_price:
            return 0.0
        
        # Calculate based on what the USER did (buy/sell), not the execution side
        if trade.user_type == TradeType.BUY:
            # User bought, profits when price goes up
            price_diff = trade.exit_price - trade.entry_price
        else:
            # User sold, profits when price goes down
            price_diff = trade.entry_price - trade.exit_price
        
        # Apply point value based on symbol
        point_value = self._get_point_value(trade.symbol)
        return price_diff * trade.volume * 1000 * point_value
    
    def _get_point_value(self, symbol: str) -> float:
        """Get point value for P&L calculations"""
        if "JPY" in symbol:
            return 0.01  # 1 pip = 0.01 for JPY pairs
        elif symbol == "XAUUSD":
            return 0.1   # 1 pip = $0.10 for Gold per 0.01 move
        else:
            return 1     # 1 pip = $1 for major pairs per 0.0001 move
    
    async def _close_fake_trade(self, trade: Trade):
        """Close fake trade using current market price"""
        price_data = await self.price_service.get_price(trade.symbol)
        if not price_data:
            raise Exception(f"No price data available for {trade.symbol}")
        
        # ✅ FIXED: Use appropriate closing price based on user's position
        if trade.user_type == TradeType.BUY:
            trade.exit_price = price_data["bid"]  # User sells at bid
        else:
            trade.exit_price = price_data["ask"]  # User covers at ask
    
    async def _close_real_trade(self, trade: Trade):
        """✅ Close real trade via MT5"""
        result = await self.mt5_service.close_position(
            ticket=trade.ticket,
            symbol=trade.symbol,
            volume=trade.volume,
            position_type=trade.exec_type.value  # Use execution type for MT5
        )
        
        if not result:
            raise Exception("MT5 position close failed")
        
        trade.exit_price = result["price"]
    
    async def get_open_positions(self, db: AsyncSession, user_id: str) -> List[PositionResponse]:
        """✅ Get all open positions for a user with correct P&L calculation"""
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
                # ✅ FIXED: Current price from user's perspective (not execution side)
                current_price = price_data["bid"] if trade.user_type == TradeType.BUY else price_data["ask"]
                
                # ✅ FIXED: Calculate unrealized P&L from user's perspective
                if trade.user_type == TradeType.BUY:
                    # User bought, profits when price goes up
                    price_diff = current_price - trade.entry_price
                else:
                    # User sold, profits when price goes down
                    price_diff = trade.entry_price - current_price
                
                point_value = self._get_point_value(trade.symbol)
                unrealized_pnl = price_diff * trade.volume * 1000 * point_value
                
                positions.append(PositionResponse(
                    id=trade.id,
                    symbol=trade.symbol,
                    user_type=trade.user_type,
                    volume=trade.volume,
                    stop_loss=trade.stop_loss,
                    entry_price=trade.entry_price,
                    current_price=current_price,
                    unrealized_pnl=unrealized_pnl,
                    open_time=trade.open_time,
                    status='EXECUTED' 
                ))
        
        return positions