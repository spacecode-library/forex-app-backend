from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from typing import List, Optional
from uuid import UUID
import logging

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
    limit: int = Query(50, le=100),
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