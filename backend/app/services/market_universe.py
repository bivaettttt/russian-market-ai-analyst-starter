from __future__ import annotations

import json
from pathlib import Path
import asyncio
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, or_, select, literal, inspect, text as sql_text
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



STOCK_BOARDS = {"TQBR", "TQBD", "TQDE", "TQPI"}
FUND_BOARDS = {"TQTF", "TQIF"}
BOND_BOARDS = {"TQOB", "TQCB", "TQIR", "TQOD", "TQOE", "TQOY"}
FUTURES_BOARDS = {"RFUD", "SPBFUT", "FUT"}
CURRENCY_BOARDS = {"CETS", "CNGD", "LICU"}


def ensure_instrument_classification_schema(db_or_engine: Any) -> None:
    bind = db_or_engine.get_bind() if hasattr(db_or_engine, "get_bind") else db_or_engine
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("instruments")}

    with bind.begin() as conn:
        if "asset_type" not in columns:
            conn.execute(
                sql_text(
                    "ALTER TABLE instruments "
                    "ADD COLUMN asset_type VARCHAR(32) NOT NULL DEFAULT 'unknown'"
                )
            )

        if "is_signal_eligible" not in columns:
            conn.execute(
                sql_text(
                    "ALTER TABLE instruments "
                    "ADD COLUMN is_signal_eligible BOOLEAN NOT NULL DEFAULT 0"
                )
            )

        conn.execute(
            sql_text(
                "CREATE INDEX IF NOT EXISTS ix_instruments_asset_type "
                "ON instruments (asset_type)"
            )
        )
        conn.execute(
            sql_text(
                "CREATE INDEX IF NOT EXISTS ix_instruments_is_signal_eligible "
                "ON instruments (is_signal_eligible)"
            )
        )


def classify_instrument(item: dict[str, Any]) -> tuple[str, bool]:
    board = _normalize_board(item.get("board"), default="TQBR")
    ticker = str(item.get("ticker") or "").upper().strip()
    name = str(item.get("name") or item.get("short_name") or "").lower()
    sector = str(item.get("sector") or "").lower()

    text_value = " ".join([ticker.lower(), name, sector])

    if board in FUTURES_BOARDS or "фьючерс" in text_value or "futures" in text_value:
        return "futures", False

    if board in CURRENCY_BOARDS or "валют" in text_value or "currency" in text_value:
        return "currency", False

    if (
        board in BOND_BOARDS
        or "облигац" in text_value
        or "офз" in text_value
        or "bond" in text_value
    ):
        return "bond", False

    if (
        board in FUND_BOARDS
        or "бпиф" in text_value
        or "пиф" in text_value
        or "etf" in text_value
        or "фонд" in text_value
    ):
        return "fund", True

    if board in STOCK_BOARDS:
        return "stock", True

    return "unknown", False


def backfill_instrument_classification(db: Session) -> dict[str, Any]:
    ensure_instrument_classification_schema(db)

    rows = db.scalars(select(Instrument).order_by(Instrument.ticker)).all()

    updated = 0
    counts: dict[str, int] = {}
    eligible_count = 0

    for instrument in rows:
        asset_type, is_signal_eligible = classify_instrument(
            {
                "ticker": instrument.ticker,
                "name": instrument.name,
                "board": instrument.board,
                "sector": instrument.sector,
            }
        )

        if instrument.asset_type != asset_type or instrument.is_signal_eligible != is_signal_eligible:
            instrument.asset_type = asset_type
            instrument.is_signal_eligible = is_signal_eligible
            updated += 1

        counts[asset_type] = counts.get(asset_type, 0) + 1

        if is_signal_eligible:
            eligible_count += 1

    db.commit()

    return {
        "ok": True,
        "total": len(rows),
        "updated": updated,
        "asset_type_counts": counts,
        "signal_eligible_count": eligible_count,
    }


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

        instrument.asset_type = asset_type
        instrument.is_signal_eligible = is_signal_eligible
        return "updated"

    db.add(
        Instrument(
            ticker=ticker,
            name=name,
            board=board,
            lot_size=lot_size,
            asset_type=asset_type,
            is_signal_eligible=is_signal_eligible,
        )
    )
    return "inserted"


async def update_moex_universe(
    db: Session,
    boards: list[str] | None = None,
    include_all_market: bool = True,
) -> dict[str, Any]:
    ensure_instrument_classification_schema(db)

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
    eligible_only: bool = False,
    asset_type: str | None = None,
) -> dict[str, Any]:
    ensure_instrument_classification_schema(db)

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

    if eligible_only:
        stmt = stmt.where(Instrument.is_signal_eligible.is_(True))

    if asset_type:
        stmt = stmt.where(Instrument.asset_type == asset_type)

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
                "asset_type": item.asset_type,
                "is_signal_eligible": item.is_signal_eligible,
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
    ensure_instrument_classification_schema(db)

    instruments_count = db.scalar(select(func.count(Instrument.id))) or 0
    signal_eligible_count = (
        db.scalar(
            select(func.count(Instrument.id)).where(
                Instrument.is_signal_eligible.is_(True)
            )
        )
        or 0
    )
    tickers_with_candles = db.scalar(select(func.count(func.distinct(Candle.ticker)))) or 0
    candles_count = db.scalar(select(func.count(Candle.id))) or 0
    latest_date = db.scalar(select(func.max(Candle.trade_date)))

    asset_type_counts = {
        str(row[0] or "unknown"): row[1]
        for row in db.execute(
            select(Instrument.asset_type, func.count(Instrument.id)).group_by(Instrument.asset_type)
        ).all()
    }

    sample = search_instruments(db=db, q=None, limit=limit, only_with_candles=False)["rows"]

    return {
        "ok": True,
        "instruments_count": instruments_count,
        "signal_eligible_count": signal_eligible_count,
        "asset_type_counts": asset_type_counts,
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


def _candle_update_state_path() -> Path:
    backend_dir = Path(__file__).resolve().parents[2]
    data_dir = backend_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "candle_update_state.json"


def _load_candle_update_state() -> dict[str, Any]:
    path = _candle_update_state_path()

    if not path.exists():
        return {"zero_rows": {}}

    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            return {"zero_rows": {}}
        data.setdefault("zero_rows", {})
        return data
    except Exception:
        return {"zero_rows": {}}


def _save_candle_update_state(state: dict[str, Any]) -> None:
    path = _candle_update_state_path()
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True))


def _is_recent_zero_row_skip(
    state: dict[str, Any],
    ticker: str,
    board: str | None,
    days: int,
    today: date,
    retry_after_days: int = 7,
) -> bool:
    zero_rows = state.get("zero_rows") or {}
    item = zero_rows.get(ticker)

    if not item:
        return False

    if item.get("board") and board and item.get("board") != board:
        return False

    if int(item.get("days") or 0) < days:
        return False

    checked_at_raw = item.get("checked_at")

    try:
        checked_at = date.fromisoformat(str(checked_at_raw))
    except Exception:
        return False

    return (today - checked_at).days < retry_after_days


def _mark_zero_row(
    state: dict[str, Any],
    ticker: str,
    board: str | None,
    days: int,
    today: date,
) -> None:
    state.setdefault("zero_rows", {})[ticker] = {
        "ticker": ticker,
        "board": board,
        "days": days,
        "checked_at": str(today),
    }


def _clear_zero_row(state: dict[str, Any], ticker: str) -> None:
    zero_rows = state.setdefault("zero_rows", {})
    zero_rows.pop(ticker, None)



async def update_candles_for_universe(
    db: Session,
    days: int = 420,
    max_tickers: int = 50,
    pause_seconds: float = 0.05,
    board: str | None = None,
) -> dict[str, Any]:
    to_date = date.today()
    from_date = to_date - timedelta(days=days)

    ensure_instrument_classification_schema(db)

    state = _load_candle_update_state()

    candle_stats = (
        select(
            Candle.ticker.label("ticker"),
            func.count(Candle.id).label("candles_count"),
            func.max(Candle.trade_date).label("latest_candle_date"),
        )
        .group_by(Candle.ticker)
        .subquery()
    )

    candles_count_expr = func.coalesce(candle_stats.c.candles_count, 0)
    latest_date_expr = func.coalesce(
        candle_stats.c.latest_candle_date,
        literal(date(1970, 1, 1)),
    )

    candidate_limit = max(max_tickers * 5, max_tickers + 200)

    stmt = (
        select(Instrument)
        .outerjoin(candle_stats, candle_stats.c.ticker == Instrument.ticker)
        .order_by(
            candles_count_expr.asc(),
            latest_date_expr.asc(),
            Instrument.ticker.asc(),
        )
        .limit(candidate_limit)
    )

    if board:
        stmt = stmt.where(Instrument.board == board)

    candidates = db.scalars(stmt).all()

    instruments: list[Instrument] = []
    skipped_recent_zero_rows: list[dict[str, Any]] = []

    for instrument in candidates:
        if _is_recent_zero_row_skip(
            state=state,
            ticker=instrument.ticker,
            board=instrument.board,
            days=days,
            today=to_date,
        ):
            skipped_recent_zero_rows.append(
                {
                    "ticker": instrument.ticker,
                    "board": instrument.board,
                    "reason": "recent_zero_rows",
                }
            )
            continue

        instruments.append(instrument)

        if len(instruments) >= max_tickers:
            break

    client = MoexClient(timeout=30.0)
    updated: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    zero_rows: list[dict[str, Any]] = []
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

            if rows:
                _clear_zero_row(state, instrument.ticker)
            else:
                _mark_zero_row(
                    state=state,
                    ticker=instrument.ticker,
                    board=instrument.board,
                    days=days,
                    today=to_date,
                )
                zero_rows.append(
                    {
                        "ticker": instrument.ticker,
                        "board": instrument.board,
                    }
                )

            updated.append(
                {
                    "ticker": instrument.ticker,
                    "board": instrument.board,
                    "rows": len(rows),
                    "saved": saved,
                }
            )
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            failed.append(
                {
                    "ticker": instrument.ticker,
                    "board": instrument.board,
                    "error": str(exc),
                }
            )

        if pause_seconds > 0:
            await asyncio.sleep(pause_seconds)

    _save_candle_update_state(state)

    return {
        "ok": True,
        "from_date": str(from_date),
        "to_date": str(to_date),
        "requested_tickers": len(instruments),
        "candidate_tickers": len(candidates),
        "updated_count": len(updated),
        "failed_count": len(failed),
        "zero_rows_count": len(zero_rows),
        "skipped_recent_zero_rows_count": len(skipped_recent_zero_rows),
        "rows_fetched": total_rows,
        "rows_saved": total_saved,
        "updated": updated[:25],
        "zero_rows": zero_rows[:25],
        "skipped_recent_zero_rows": skipped_recent_zero_rows[:25],
        "failed": failed[:25],
        "note": "Батч пропускает тикеры, по которым недавно MOEX вернул 0 свечей, и берёт следующие кандидаты.",
    }
