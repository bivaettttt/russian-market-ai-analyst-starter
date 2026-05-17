from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Candle, Instrument


PERIOD_DAYS = {
    "1D": 10,
    "1W": 21,
    "1M": 45,
    "3M": 110,
    "6M": 210,
    "1Y": 420,
    "ALL": 3650,
}

DEFAULT_BOARDS = [
    "TQBR",  # акции
    "TQTF",  # ETF / БПИФ
    "TQIF",  # фонды
]


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


def _candidate_boards(instrument: Instrument | None) -> list[str]:
    boards: list[str] = []

    board = (getattr(instrument, "board", None) or "").upper().strip()

    if board:
        boards.append(board)

    for item in DEFAULT_BOARDS:
        if item not in boards:
            boards.append(item)

    return boards


def _normalize_period(period: str | None) -> str:
    value = (period or "1Y").upper().strip()

    if value in {"ВСЕ", "ALL"}:
        return "ALL"

    if value not in PERIOD_DAYS:
        return "1Y"

    return value


def _local_daily_candles(
    db: Session,
    ticker: str,
    period: str,
    limit: int,
) -> list[dict[str, Any]]:
    normalized_ticker = ticker.upper().strip()

    query = (
        select(Candle)
        .where(Candle.ticker == normalized_ticker)
        .order_by(Candle.trade_date)
    )

    days = PERIOD_DAYS.get(period)

    if days is not None and period != "ALL":
        from_date = date.today() - timedelta(days=days)
        query = query.where(Candle.trade_date >= from_date)

    candles = list(db.scalars(query).all())

    if limit > 0:
        candles = candles[-limit:]

    rows: list[dict[str, Any]] = []

    for item in candles:
        close = _to_float(item.close)

        if close is None:
            continue

        rows.append(
            {
                "time": _to_date_string(item.trade_date),
                "date": _to_date_string(item.trade_date),
                "open": _to_float(item.open),
                "high": _to_float(item.high),
                "low": _to_float(item.low),
                "close": close,
                "volume": _to_float(item.volume),
                "value": _to_float(item.value),
                "source": "local_daily",
            }
        )

    return rows


def _moex_candles_url(
    ticker: str,
    board: str,
    from_date: date,
    till_date: date,
    interval: int,
    start: int,
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
            "start": str(start),
            "iss.meta": "off",
        }
    )

    return f"{base}?{params}"


def _fetch_moex_candles_for_board(
    ticker: str,
    board: str,
    period: str,
    limit: int,
) -> list[dict[str, Any]]:
    today = date.today()
    days = PERIOD_DAYS.get(period, 420)
    from_date = today - timedelta(days=days)

    if period == "1D":
        interval = 10
    elif period == "1W":
        interval = 60
    else:
        interval = 24

    rows: list[dict[str, Any]] = []
    start = 0

    for _ in range(20):
        url = _moex_candles_url(
            ticker=ticker.upper().strip(),
            board=board,
            from_date=from_date,
            till_date=today,
            interval=interval,
            start=start,
        )

        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception:
            break

        candles = payload.get("candles") or {}
        columns = candles.get("columns") or []
        data = candles.get("data") or []

        if not data:
            break

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
                    "source": "moex_candles",
                    "board": board,
                    "interval": interval,
                }
            )

        start += len(data)

        if len(data) < 500:
            break

        if limit > 0 and len(rows) >= limit:
            break

    if limit > 0:
        rows = rows[-limit:]

    return rows


def _fetch_moex_candles(
    ticker: str,
    boards: list[str],
    period: str,
    limit: int,
) -> tuple[list[dict[str, Any]], str | None]:
    for board in boards:
        rows = _fetch_moex_candles_for_board(
            ticker=ticker,
            board=board,
            period=period,
            limit=limit,
        )

        if len(rows) >= 2:
            return rows, board

    return [], None


def _quality_for_rows(rows: list[dict[str, Any]]) -> tuple[str, str]:
    count = len(rows)

    if count == 0:
        return "empty", "История торгов по инструменту не найдена."

    if count < 2:
        return "single_point", "Найдена только одна свеча. Этого недостаточно для построения графика."

    if count < 10:
        return "sparse", f"История торгов очень короткая: найдено {count} свечей. График может выглядеть неполным."

    return "ok", "Данных достаточно для построения графика."


def build_ticker_chart_data(
    db: Session,
    ticker: str,
    period: str = "1Y",
    limit: int = 1000,
) -> dict[str, Any]:
    normalized_ticker = ticker.upper().strip()
    normalized_period = _normalize_period(period)

    instrument = _instrument_for_ticker(db=db, ticker=normalized_ticker)
    boards = _candidate_boards(instrument)

    local_rows = _local_daily_candles(
        db=db,
        ticker=normalized_ticker,
        period=normalized_period,
        limit=limit,
    )

    rows = local_rows
    source = "local_daily"
    board_used = boards[0] if boards else None

    # Если локально мало данных, пробуем MOEX напрямую по нескольким board.
    if len(rows) < 10:
        moex_rows, moex_board = _fetch_moex_candles(
            ticker=normalized_ticker,
            boards=boards,
            period=normalized_period,
            limit=limit,
        )

        if len(moex_rows) > len(rows):
            rows = moex_rows
            source = "moex_candles"
            board_used = moex_board

    data_quality, quality_message = _quality_for_rows(rows)
    latest = rows[-1] if rows else None

    return {
        "ok": True,
        "ticker": normalized_ticker,
        "period": normalized_period,
        "board": board_used,
        "candidate_boards": boards,
        "source": source,
        "local_count": len(local_rows),
        "count": len(rows),
        "data_quality": data_quality,
        "quality_message": quality_message,
        "latest": latest,
        "candles": rows,
        "note": (
            "График сначала использует локальные свечи. "
            "Если локальной истории мало, backend пробует загрузить свечи напрямую из MOEX ISS."
        ),
    }

# --- Ticker alias resolver wrapper ---
from app.services.ticker_aliases import apply_alias_metadata, resolve_ticker_alias

_build_ticker_chart_data_without_alias = build_ticker_chart_data


def build_ticker_chart_data(
    db: Session,
    ticker: str,
    period: str = "1Y",
    limit: int = 1000,
) -> dict[str, Any]:
    resolution = resolve_ticker_alias(ticker)
    result = _build_ticker_chart_data_without_alias(
        db=db,
        ticker=resolution["resolved_ticker"],
        period=period,
        limit=limit,
    )

    if isinstance(result, dict):
        apply_alias_metadata(result, resolution)

    return result


_ALIAS_AWARE_TICKER_CHART_WRAPPER = True

