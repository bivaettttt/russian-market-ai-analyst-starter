from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Candle, Instrument


PERIOD_DAYS = {
    "1D": 3,
    "1W": 10,
    "1M": 35,
    "3M": 100,
    "6M": 190,
    "1Y": 380,
}


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None

        return float(value)
    except (TypeError, ValueError):
        return None


def _to_date_string(value: Any) -> str | None:
    if value is None:
        return None

    return str(value)


def _instrument_for_ticker(db: Session, ticker: str) -> Instrument | None:
    return db.scalar(
        select(Instrument)
        .where(Instrument.ticker == ticker.upper().strip())
        .limit(1)
    )


def _local_daily_candles(
    db: Session,
    ticker: str,
    period: str,
    limit: int,
) -> list[dict[str, Any]]:
    query = (
        select(Candle)
        .where(Candle.ticker == ticker.upper().strip())
        .order_by(Candle.trade_date)
    )

    days = PERIOD_DAYS.get(period)

    if days is not None:
        from_date = date.today() - timedelta(days=days)
        query = query.where(Candle.trade_date >= from_date)

    candles = list(db.scalars(query).all())

    if limit > 0:
        candles = candles[-limit:]

    return [
        {
            "time": _to_date_string(item.trade_date),
            "date": _to_date_string(item.trade_date),
            "open": _to_float(item.open),
            "high": _to_float(item.high),
            "low": _to_float(item.low),
            "close": _to_float(item.close),
            "volume": _to_float(item.volume),
            "value": _to_float(item.value),
            "source": "local_daily",
        }
        for item in candles
        if _to_float(item.close) is not None
    ]


def _moex_candles_url(
    ticker: str,
    board: str,
    from_date: date,
    till_date: date,
    interval: int,
) -> str:
    base = (
        "https://iss.moex.com/iss/engines/stock/markets/shares/"
        f"boards/{urllib.parse.quote(board)}/"
        f"securities/{urllib.parse.quote(ticker)}/candles.json"
    )

    params = urllib.parse.urlencode(
        {
            "from": str(from_date),
            "till": str(till_date),
            "interval": str(interval),
            "iss.meta": "off",
        }
    )

    return f"{base}?{params}"


def _fetch_moex_intraday_candles(
    ticker: str,
    board: str,
    period: str,
    limit: int,
) -> list[dict[str, Any]]:
    today = date.today()

    if period == "1D":
        from_date = today - timedelta(days=5)
        interval = 10
    elif period == "1W":
        from_date = today - timedelta(days=14)
        interval = 60
    else:
        return []

    url = _moex_candles_url(
        ticker=ticker.upper().strip(),
        board=board,
        from_date=from_date,
        till_date=today,
        interval=interval,
    )

    try:
        with urllib.request.urlopen(url, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return []

    candles = payload.get("candles") or {}
    columns = candles.get("columns") or []
    data = candles.get("data") or []

    rows: list[dict[str, Any]] = []

    for raw_row in data:
        row = dict(zip(columns, raw_row))

        close = _to_float(row.get("close"))

        if close is None:
            continue

        rows.append(
            {
                "time": row.get("begin") or row.get("end"),
                "date": row.get("begin") or row.get("end"),
                "open": _to_float(row.get("open")),
                "high": _to_float(row.get("high")),
                "low": _to_float(row.get("low")),
                "close": close,
                "volume": _to_float(row.get("volume")),
                "value": _to_float(row.get("value")),
                "source": "moex_intraday",
                "interval": interval,
            }
        )

    if limit > 0:
        rows = rows[-limit:]

    return rows


def build_ticker_chart_data(
    db: Session,
    ticker: str,
    period: str = "1Y",
    limit: int = 1000,
) -> dict[str, Any]:
    normalized_ticker = ticker.upper().strip()
    normalized_period = (period or "1Y").upper().strip()

    if normalized_period in {"ALL", "ВСЕ"}:
        normalized_period = "ALL"

    instrument = _instrument_for_ticker(db=db, ticker=normalized_ticker)
    board = (getattr(instrument, "board", None) or "TQBR").upper()

    rows: list[dict[str, Any]] = []

    if normalized_period in {"1D", "1W"}:
        rows = _fetch_moex_intraday_candles(
            ticker=normalized_ticker,
            board=board,
            period=normalized_period,
            limit=limit,
        )

    if not rows:
        rows = _local_daily_candles(
            db=db,
            ticker=normalized_ticker,
            period=normalized_period,
            limit=limit,
        )

    latest = rows[-1] if rows else None

    return {
        "ok": True,
        "ticker": normalized_ticker,
        "period": normalized_period,
        "board": board,
        "count": len(rows),
        "latest": latest,
        "candles": rows,
        "note": (
            "1D/1W пытаются использовать intraday MOEX candles; "
            "если данных нет, используется локальная дневная история."
        ),
    }
