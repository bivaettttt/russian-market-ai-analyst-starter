from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.market_universe import (
    search_instruments,
    universe_summary,
    update_candles_for_universe,
    update_moex_universe,
)

router = APIRouter()


@router.get("/tickers/search")
def tickers_search(
    q: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    only_with_candles: bool = Query(False),
    eligible_only: bool = Query(False),
    asset_type: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return search_instruments(
        db=db,
        q=q,
        limit=limit,
        only_with_candles=only_with_candles,
        eligible_only=eligible_only,
        asset_type=asset_type,
    )


@router.get("/tickers/universe")
def tickers_universe(
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return universe_summary(db=db, limit=limit)


@router.post("/system/update-universe")
async def system_update_universe(
    boards: str = Query("TQBR,TQTF,TQIF,TQPI"),
    include_all_market: bool = Query(True),
    db: Session = Depends(get_db),
):
    board_list = [item.strip().upper() for item in boards.split(",") if item.strip()]
    return await update_moex_universe(
        db=db,
        boards=board_list or ["TQBR"],
        include_all_market=include_all_market,
    )


@router.post("/system/update-candles/all")
async def system_update_candles_all(
    days: int = Query(420, ge=30, le=2500),
    max_tickers: int = Query(50, ge=1, le=500),
    board: str | None = Query(None),
    pause_seconds: float = Query(0.05, ge=0, le=2),
    db: Session = Depends(get_db),
):
    return await update_candles_for_universe(
        db=db,
        days=days,
        max_tickers=max_tickers,
        pause_seconds=pause_seconds,
        board=board,
    )
