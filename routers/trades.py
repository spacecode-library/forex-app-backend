from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from typing import List, Optional
from uuid import UUID
import logging
from pydantic import BaseModel

from database import get_database
from models.user import User
from models.trade import Trade, TradeStatus
from schemas.trade import TradeCreate, TradeResponse, PositionResponse
from dependencies import get_current_user
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/place", response_model=TradeResponse)
async def place_trade(
    trade_data: TradeCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database)
):
    """Place a new trade"""
    # Import here to avoid circular dependency
    from main import app
    trade_service = app.state.trade_service
    
    # Validate symbol
    if trade_data.symbol not in settings.SYMBOLS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Symbol {trade_data.symbol} not supported"
        )
    
    # Check balance (simplified margin check)
    margin_required = trade_data.volume * 1000
    if current_user.balance < margin_required:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient balance"
        )
    
    try:
        trade = await trade_service.place_trade(db, current_user, trade_data)
        logger.info(f"Trade placed: {trade.ticket} for user {current_user.username}")
        return trade
    except Exception as e:
        logger.error(f"Trade placement failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/close/{trade_id}", response_model=TradeResponse)
async def close_trade(
    trade_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database)
):
    """Close an open trade"""
    from main import app
    trade_service = app.state.trade_service
    
    result = await db.execute(
        select(Trade).where(
            and_(
                Trade.id == trade_id,
                Trade.users_id == current_user.id
            )
        )
    )
    trade = result.scalar_one_or_none()
    
    if not trade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trade not found"
        )
    
    if trade.status != TradeStatus.EXECUTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trade is not open"
        )
    
    try:
        closed_trade = await trade_service.close_trade(db, trade)
        logger.info(f"Trade closed: {closed_trade.ticket} for user {current_user.username}")
        return closed_trade
    except Exception as e:
        logger.error(f"Trade close failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/history", response_model=List[TradeResponse])
async def get_trade_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database),
    limit: int = Query(50, le=1000),
    offset: int = Query(0, ge=0)
):
    """Get user's trade history"""
    result = await db.execute(
        select(Trade)
        .where(Trade.users_id == current_user.id)
        .order_by(desc(Trade.open_time))
        .limit(limit)
        .offset(offset)
    )
    trades = result.scalars().all()
    return trades

@router.get("/positions", response_model=List[PositionResponse])
async def get_positions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database),
    force_refresh: bool = Query(False, description="Force refresh positions from database")
):
    """Get user's open positions"""
    from main import app
    trade_service = app.state.trade_service
    
    try:
        logger.info(f"Fetching positions for user {current_user.username} (force_refresh={force_refresh})")
        
        # Get open positions from database
        result = await db.execute(
            select(Trade).where(
                and_(
                    Trade.users_id == current_user.id,
                    Trade.status == TradeStatus.EXECUTED
                )
            ).order_by(desc(Trade.open_time))
        )
        trades = result.scalars().all()
        
        logger.info(f"Found {len(trades)} open trades in database for user {current_user.username}")
        
        # Convert to position responses with current prices
        positions = await trade_service.get_open_positions(db, str(current_user.id))
        
        logger.info(f"Returning {len(positions)} positions with current prices")
        
        # Log each position for debugging
        for pos in positions:
            logger.debug(f"Position: {pos.symbol} {pos.user_type} {pos.volume} lots, P&L: {pos.unrealized_pnl}")
        
        return positions
        
    except Exception as e:
        logger.error(f"Failed to fetch positions for user {current_user.username}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch positions"
        )

@router.get("/position/{position_id}", response_model=PositionResponse)
async def get_specific_position(
    position_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database)
):
    """Get a specific position by ID"""
    from main import app
    trade_service = app.state.trade_service
    
    try:
        # Check if trade exists and belongs to user
        result = await db.execute(
            select(Trade).where(
                and_(
                    Trade.id == position_id,
                    Trade.users_id == current_user.id,
                    Trade.status == TradeStatus.EXECUTED
                )
            )
        )
        trade = result.scalar_one_or_none()
        
        if not trade:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Position not found or not open"
            )
        
        # Get current price data
        price_data = await trade_service.price_service.get_price(trade.symbol)
        if not price_data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to get current price"
            )
        
        current_price = price_data["bid"] if trade.exec_type.value == "sell" else price_data["ask"]
        
        # Calculate unrealized P&L
        if trade.exec_type.value == "sell":
            unrealized_pnl = (trade.entry_price - current_price) * trade.volume * 1000
        else:
            unrealized_pnl = (current_price - trade.entry_price) * trade.volume * 1000
        
        position = PositionResponse(
            symbol=trade.symbol,
            user_type=trade.user_type,
            volume=trade.volume,
            entry_price=trade.entry_price,
            current_price=current_price,
            unrealized_pnl=unrealized_pnl,
            open_time=trade.open_time
        )
        
        logger.info(f"Retrieved specific position {position_id} for user {current_user.username}")
        return position
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch position {position_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch position"
        )

@router.get("/debug/positions")
async def debug_positions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database)
):
    """Debug endpoint to check position data"""
    try:
        # Get all trades for user
        result = await db.execute(
            select(Trade).where(Trade.users_id == current_user.id)
            .order_by(desc(Trade.open_time))
        )
        all_trades = result.scalars().all()
        
        # Get only open trades
        open_trades_result = await db.execute(
            select(Trade).where(
                and_(
                    Trade.users_id == current_user.id,
                    Trade.status == TradeStatus.EXECUTED
                )
            ).order_by(desc(Trade.open_time))
        )
        open_trades = open_trades_result.scalars().all()
        
        debug_info = {
            "user_id": str(current_user.id),
            "username": current_user.username,
            "total_trades": len(all_trades),
            "open_trades": len(open_trades),
            "all_trades": [
                {
                    "id": str(trade.id),
                    "ticket": trade.ticket,
                    "symbol": trade.symbol,
                    "user_type": trade.user_type.value,
                    "volume": float(trade.volume),
                    "status": trade.status.value,
                    "entry_price": float(trade.entry_price) if trade.entry_price else None,
                    "open_time": trade.open_time.isoformat(),
                    "is_fake": trade.is_fake
                }
                for trade in all_trades
            ],
            "open_trades_details": [
                {
                    "id": str(trade.id),
                    "ticket": trade.ticket,
                    "symbol": trade.symbol,
                    "user_type": trade.user_type.value,
                    "exec_type": trade.exec_type.value,
                    "volume": float(trade.volume),
                    "entry_price": float(trade.entry_price),
                    "open_time": trade.open_time.isoformat(),
                }
                for trade in open_trades
            ]
        }
        
        logger.info(f"Debug info for user {current_user.username}: {len(open_trades)} open positions")
        return debug_info
        
    except Exception as e:
        logger.error(f"Debug positions failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Debug failed"
        )

@router.get("/summary")
async def get_trading_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database)
):
    """Get trading summary statistics"""
    # Get closed trades for profit calculation
    result = await db.execute(
        select(Trade).where(
            and_(
                Trade.users_id == current_user.id,
                Trade.status == TradeStatus.CLOSED
            )
        )
    )
    closed_trades = result.scalars().all()
    
    total_profit = sum(trade.profit for trade in closed_trades)
    total_trades = len(closed_trades)
    winning_trades = len([t for t in closed_trades if t.profit > 0])
    
    # Get open positions count
    open_result = await db.execute(
        select(Trade).where(
            and_(
                Trade.users_id == current_user.id,
                Trade.status == TradeStatus.EXECUTED
            )
        )
    )
    open_positions = len(open_result.scalars().all())
    
    summary = {
        "balance": current_user.balance,
        "total_profit": total_profit,
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "win_rate": (winning_trades / total_trades * 100) if total_trades > 0 else 0,
        "open_positions": open_positions
    }
    
    logger.info(f"Trading summary for {current_user.username}: {summary}")
    return summary

@router.get("/account", response_model=dict)
async def get_account_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database)
):
    """
    Get account information including leverage and margin usage.
    """
    from main import app
    trade_service = app.state.trade_service
    
    try:
        account_info = await trade_service.get_account_info(db, current_user)
        return account_info
    except Exception as e:
        logger.error(f"Failed to get account info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve account information"
        )
    
@router.get("/pending-orders")
async def get_pending_orders(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database)
):
    """Get user's pending limit orders"""
    from main import app
    trade_service = app.state.trade_service
    
    user_pending = []
    for ticket, trade in trade_service.pending_limit_orders.items():
        if trade.users_id == current_user.id:
            user_pending.append({
                "id": str(trade.id),
                "ticket": trade.ticket,
                "symbol": trade.symbol,
                "user_type": trade.user_type.value,
                "volume": float(trade.volume),
                "target_price": float(trade.entry_price),
                "stop_loss": float(trade.stop_loss) if trade.stop_loss else None,
                "take_profit": float(trade.take_profit) if trade.take_profit else None,
                "status": "PENDING"
            })
    
    return user_pending


class TradeUpdateRequest(BaseModel):
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

# Add to trades router
@router.put("/update/{trade_id}")
async def update_trade(
    trade_id: UUID,
    update: TradeUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database)
):
    """Update stop loss and take profit for existing position"""
    result = await db.execute(
        select(Trade).where(
            and_(
                Trade.id == trade_id,
                Trade.users_id == current_user.id,
                Trade.status == TradeStatus.EXECUTED
            )
        )
    )
    trade = result.scalar_one_or_none()
    
    if not trade:
        raise HTTPException(status_code=404, detail="Position not found")
    
    # Update SL/TP
    if update.stop_loss is not None:
        trade.stop_loss = update.stop_loss
    if update.take_profit is not None:
        trade.take_profit = update.take_profit
    
    await db.commit()
    await db.refresh(trade)
    
    return {"message": "Position updated successfully"}

@router.post("/cancel/{trade_id}")
async def cancel_pending_order(
    trade_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database)
):
    """Cancel a pending limit order"""
    from main import app
    trade_service = app.state.trade_service
    
    # Get the trade from database
    result = await db.execute(
        select(Trade).where(
            and_(
                Trade.id == trade_id,
                Trade.users_id == current_user.id,
                Trade.status == TradeStatus.PENDING
            )
        )
    )
    trade = result.scalar_one_or_none()
    
    if not trade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending order not found"
        )
    
    try:
        # Remove from pending in-memory dict
        if trade.ticket in trade_service.pending_limit_orders:
            del trade_service.pending_limit_orders[trade.ticket]
            logger.info(f"Removed pending order {trade.ticket} from monitoring")

        # Update trade status
        trade.status = TradeStatus.CANCELLED

        # Get user
        user_result = await db.execute(select(User).where(User.id == current_user.id))
        user = user_result.scalar_one()

        # Refund both margin and commission
        margin_refund = trade.margin_required or await trade_service.calculate_margin_required(user, trade.symbol, trade.volume)
        commission_refund = trade.volume * trade_service.commission_per_lot
        total_refund = margin_refund + commission_refund

        user.balance += total_refund

        # Update commission in DB
        trade.commission = 0.0

        await db.commit()
        await db.refresh(trade)

        logger.info(f"Pending order cancelled: {trade.ticket}, Refunded: ${total_refund:.2f}")

        return {
            "message": f"Order {trade.ticket} cancelled successfully",
            "ticket": trade.ticket,
            "refunded_margin": margin_refund,
            "refunded_commission": commission_refund,
            "trade": trade
        }        
    except Exception as e:
        logger.error(f"Failed to cancel order {trade.ticket}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel order"
        )