from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Candle, Instrument
from app.services.moex_client import MoexClient

PRIMARY_BOARD_PRIORITY = {
    "TQBR": 1,
    "TQTF": 2,
    "TQIF": 3,
    "TQPI": 4,
}


def _to_int(value: Any, default: int = 1) -> int:
    try:
        if value is None:
            return default
        result = int(float(value))
        return result if result > 0 else default
    except (TypeError, ValueError):
        return default



def _normalize_board(value: Any, default: str = "TQBR") -> str:
    raw = str(value or "").upper().strip()
    if not raw:
        return default

    candidates = [item.strip() for item in raw.replace(";", ",").split(",") if item.strip()]
    if not candidates:
        return default

    return sorted(candidates, key=lambda board: PRIMARY_BOARD_PRIORITY.get(board, 99))[0]


def _choose_better(existing: Instrument | None, item: dict[str, Any]) -> bool:
    if existing is None:
        return True

    old_priority = PRIMARY_BOARD_PRIORITY.get(existing.board or "", 99)
    new_priority = PRIMARY_BOARD_PRIORITY.get(str(item.get("board") or ""), 99)
    return new_priority < old_priority


def upsert_instrument(db: Session, item: dict[str, Any]) -> str | None:
    ticker = str(item.get("ticker") or "").upper().strip()
    if not ticker:
        return None

    board = _normalize_board(item.get("board"), default="TQBR")
    name = item.get("name") or item.get("short_name") or ticker
    lot_size = _to_int(item.get("lot_size"), default=1)

    instrument = db.scalar(select(Instrument).where(Instrument.ticker == ticker))

    if instrument:
        if _choose_better(instrument, {**item, "board": board}):
            instrument.board = board
            instrument.name = name
            instrument.lot_size = lot_size
        elif not instrument.name:
            instrument.name = name
        return "updated"

    db.add(Instrument(ticker=ticker, name=name, board=board, lot_size=lot_size))
    return "inserted"


async def update_moex_universe(
    db: Session,
    boards: list[str] | None = None,
    include_all_market: bool = True,
) -> dict[str, Any]:
    client = MoexClient(timeout=35.0)
    items: list[dict[str, Any]] = []

    if include_all_market and hasattr(client, "get_all_share_securities"):
        items.extend(await client.get_all_share_securities())

    for board in boards or ["TQBR"]:
        items.extend(await client.get_board_securities(board=board))

    inserted = 0
    updated = 0
    skipped = 0
    seen: set[str] = set()

    for item in items:
        ticker = str(item.get("ticker") or "").upper().strip()
        if not ticker:
            skipped += 1
            continue

        # Оставляем один лучший board на тикер, но не теряем бумаги с одинаковым SECID.
        result = upsert_instrument(db, item)
        if result == "inserted":
            inserted += 1
        elif result == "updated":
            updated += 1
        else:
            skipped += 1
        seen.add(ticker)

    db.commit()

    return {
        "ok": True,
        "fetched": len(items),
        "unique_tickers": len(seen),
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "boards": boards or ["TQBR"],
        "include_all_market": include_all_market,
    }


def search_instruments(
    db: Session,
    q: str | None = None,
    limit: int = 20,
    only_with_candles: bool = False,
) -> dict[str, Any]:
    query_text = (q or "").strip()

    stmt = select(Instrument)

    if query_text:
        like = f"%{query_text}%"
        stmt = stmt.where(
            or_(
                Instrument.ticker.ilike(like),
                Instrument.name.ilike(like),
                Instrument.sector.ilike(like),
            )
        )

    if only_with_candles:
        stmt = stmt.where(
            Instrument.ticker.in_(select(Candle.ticker).distinct())
        )

    rows = db.scalars(stmt.order_by(Instrument.ticker).limit(limit)).all()

    candle_counts = {
        row[0]: row[1]
        for row in db.execute(
            select(Candle.ticker, func.count(Candle.id))
            .where(Candle.ticker.in_([item.ticker for item in rows] or ["__none__"]))
            .group_by(Candle.ticker)
        ).all()
    }

    latest_dates = {
        row[0]: row[1]
        for row in db.execute(
            select(Candle.ticker, func.max(Candle.trade_date))
            .where(Candle.ticker.in_([item.ticker for item in rows] or ["__none__"]))
            .group_by(Candle.ticker)
        ).all()
    }

    return {
        "ok": True,
        "query": query_text,
        "count": len(rows),
        "rows": [
            {
                "ticker": item.ticker,
                "name": item.name,
                "board": item.board,
                "sector": item.sector,
                "lot_size": item.lot_size,
                "candles_count": candle_counts.get(item.ticker, 0),
                "latest_candle_date": str(latest_dates.get(item.ticker)) if latest_dates.get(item.ticker) else None,
                "ticker_url": f"/tickers/{item.ticker}",
                "forecast_url": f"/signals/consumer/{item.ticker}.json",
            }
            for item in rows
        ],
    }


def universe_summary(db: Session, limit: int = 50) -> dict[str, Any]:
    instruments_count = db.scalar(select(func.count(Instrument.id))) or 0
    tickers_with_candles = db.scalar(select(func.count(func.distinct(Candle.ticker)))) or 0
    candles_count = db.scalar(select(func.count(Candle.id))) or 0
    latest_date = db.scalar(select(func.max(Candle.trade_date)))

    sample = search_instruments(db=db, q=None, limit=limit, only_with_candles=False)["rows"]

    return {
        "ok": True,
        "instruments_count": instruments_count,
        "tickers_with_candles": tickers_with_candles,
        "candles_count": candles_count,
        "latest_candle_date": str(latest_date) if latest_date else None,
        "sample": sample,
    }


def _save_candle_rows(db: Session, rows: list[dict[str, Any]]) -> int:
    saved = 0
    for row in rows:
        trade_date_raw = row.get("trade_date")
        if not trade_date_raw:
            continue
        trade_date = date.fromisoformat(str(trade_date_raw)[:10])

        existing = db.scalar(
            select(Candle).where(
                Candle.ticker == row.get("ticker"),
                Candle.board == row.get("board"),
                Candle.trade_date == trade_date,
            )
        )

        if existing:
            existing.open = row.get("open")
            existing.high = row.get("high")
            existing.low = row.get("low")
            existing.close = row.get("close")
            existing.volume = row.get("volume")
            existing.value = row.get("value")
        else:
            db.add(
                Candle(
                    ticker=row["ticker"],
                    board=row.get("board") or "TQBR",
                    trade_date=trade_date,
                    open=row.get("open"),
                    high=row.get("high"),
                    low=row.get("low"),
                    close=row.get("close"),
                    volume=row.get("volume"),
                    value=row.get("value"),
                )
            )
        saved += 1

    return saved


async def update_candles_for_universe(
    db: Session,
    days: int = 420,
    max_tickers: int = 50,
    pause_seconds: float = 0.05,
    board: str | None = None,
) -> dict[str, Any]:
    to_date = date.today()
    from_date = to_date - timedelta(days=days)

    stmt = select(Instrument).order_by(Instrument.ticker).limit(max_tickers)
    if board:
        stmt = stmt.where(Instrument.board == board)
    instruments = db.scalars(stmt).all()

    client = MoexClient(timeout=30.0)
    updated: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    total_rows = 0
    total_saved = 0

    for instrument in instruments:
        try:
            rows = await client.get_daily_candles(
                ticker=instrument.ticker,
                from_date=from_date,
                to_date=to_date,
                board=instrument.board or "TQBR",
            )
            saved = _save_candle_rows(db, rows)
            db.commit()
            total_rows += len(rows)
            total_saved += saved
            updated.append({"ticker": instrument.ticker, "board": instrument.board, "rows": len(rows), "saved": saved})
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            failed.append({"ticker": instrument.ticker, "board": instrument.board, "error": str(exc)})

        if pause_seconds > 0:
            await asyncio.sleep(pause_seconds)

    return {
        "ok": True,
        "from_date": str(from_date),
        "to_date": str(to_date),
        "requested_tickers": len(instruments),
        "updated_count": len(updated),
        "failed_count": len(failed),
        "rows_fetched": total_rows,
        "rows_saved": total_saved,
        "updated": updated[:25],
        "failed": failed[:25],
        "note": "Для полного рынка запускайте батчами: max_tickers=50/100, пока tickers_with_candles не догонит universe.",
    }
