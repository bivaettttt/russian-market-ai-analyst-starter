from __future__ import annotations

import time
from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Candle, Instrument
from app.services.data_coverage_diagnostics import build_data_coverage_diagnostics
from app.services.market_universe import classify_instrument, ensure_instrument_classification_schema


DEFAULT_SHARE_BOARDS = ["TQBR"]
DEFAULT_FUND_BOARDS = ["TQTF", "TQIF"]
DEFAULT_BOND_BOARDS = ["TQOB"]
SUPPORTED_MARKETS = {"shares", "bonds"}


def normalize_tickers(value: str | list[str] | None) -> list[str] | None:
    if value is None:
        return None
    items = value.split(",") if isinstance(value, str) else value
    normalized: list[str] = []
    seen: set[str] = set()
    for item in items:
        ticker = str(item or "").upper().strip()
        if ticker and ticker not in seen:
            normalized.append(ticker)
            seen.add(ticker)
    return normalized or None


def build_date_range(
    *,
    days: int = 900,
    from_date: str | None = None,
    till_date: str | None = None,
) -> tuple[str, str]:
    till = date.fromisoformat(till_date) if till_date else date.today()
    start = date.fromisoformat(from_date) if from_date else till - timedelta(days=max(1, days))
    if start > till:
        start, till = till, start
    return start.isoformat(), till.isoformat()


def parse_moex_table(payload: dict[str, Any], block_name: str) -> list[dict[str, Any]]:
    block = payload.get(block_name) or {}
    columns = block.get("columns") or []
    data = block.get("data") or []
    return [dict(zip(columns, row, strict=False)) for row in data]


def parse_moex_security_rows(payload: dict[str, Any], *, default_board: str, market: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in parse_moex_table(payload, "securities"):
        ticker = str(raw.get("SECID") or "").upper().strip()
        if not ticker:
            continue
        board = str(raw.get("BOARDID") or raw.get("PRIMARY_BOARDID") or default_board or "TQBR").upper().strip()
        rows.append(
            {
                "ticker": ticker,
                "name": raw.get("SECNAME") or raw.get("NAME") or raw.get("SHORTNAME") or ticker,
                "short_name": raw.get("SHORTNAME") or raw.get("SECNAME") or ticker,
                "board": board,
                "market": market,
                "lot_size": raw.get("LOTSIZE") or raw.get("LOTVALUE") or 1,
            }
        )
    return rows


def parse_moex_history_rows(payload: dict[str, Any], *, ticker: str, board: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in parse_moex_table(payload, "candles"):
        trade_date = str(raw.get("begin") or raw.get("TRADEDATE") or "")[:10]
        rows.append(
            {
                "ticker": ticker.upper(),
                "board": board.upper(),
                "trade_date": trade_date,
                "open": raw.get("open") or raw.get("OPEN"),
                "high": raw.get("high") or raw.get("HIGH"),
                "low": raw.get("low") or raw.get("LOW"),
                "close": raw.get("close") or raw.get("CLOSE"),
                "volume": raw.get("volume") or raw.get("VOLUME"),
                "value": raw.get("value") or raw.get("VALUE"),
            }
        )
    return rows


def _fetch_json(client: httpx.Client, url: str, params: dict[str, Any], retries: int = 2) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < retries:
                time.sleep(0.4 * (attempt + 1))
    raise RuntimeError(str(last_error) if last_error else "MOEX request failed")


def _fetch_paged_table(
    client: httpx.Client,
    url: str,
    *,
    block_name: str,
    params: dict[str, Any] | None = None,
    max_rows: int = 20000,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    start = 0
    base_params = {"iss.meta": "off", **(params or {})}
    while len(result) < max_rows:
        payload = _fetch_json(client, url, {**base_params, "start": start})
        rows = parse_moex_table(payload, block_name)
        if not rows:
            break
        result.extend(rows)
        if len(rows) < 100:
            break
        start += len(rows)
    return result[:max_rows]


def _security_fetch_targets(
    *,
    markets: list[str] | None,
    boards: list[str] | None,
    include_etf: bool,
    include_bonds: bool,
) -> list[tuple[str, str]]:
    requested_markets = [str(item).strip().lower() for item in (markets or ["shares"]) if str(item).strip()]
    requested_markets = [item for item in requested_markets if item in SUPPORTED_MARKETS] or ["shares"]
    requested_boards = [str(item).upper().strip() for item in boards or [] if str(item).strip()]

    targets: list[tuple[str, str]] = []
    if "shares" in requested_markets:
        for board in requested_boards or DEFAULT_SHARE_BOARDS:
            targets.append(("shares", board))
        if include_etf:
            for board in DEFAULT_FUND_BOARDS:
                if ("shares", board) not in targets:
                    targets.append(("shares", board))
    if include_bonds or "bonds" in requested_markets:
        for board in requested_boards or DEFAULT_BOND_BOARDS:
            targets.append(("bonds", board))
    return targets


def _upsert_instrument(db: Session, item: dict[str, Any], *, dry_run: bool) -> str | None:
    ticker = str(item.get("ticker") or "").upper().strip()
    if not ticker:
        return None
    asset_type, is_signal_eligible = classify_instrument(item)
    existing = db.scalar(select(Instrument).where(Instrument.ticker == ticker))
    if existing:
        if not dry_run:
            existing.name = item.get("name") or item.get("short_name") or existing.name or ticker
            existing.board = str(item.get("board") or existing.board or "TQBR").upper()
            existing.lot_size = _safe_int(item.get("lot_size"), existing.lot_size or 1)
            existing.asset_type = asset_type
            existing.is_signal_eligible = is_signal_eligible
        return "updated"
    if not dry_run:
        db.add(
            Instrument(
                ticker=ticker,
                name=item.get("name") or item.get("short_name") or ticker,
                board=str(item.get("board") or "TQBR").upper(),
                lot_size=_safe_int(item.get("lot_size"), 1),
                asset_type=asset_type,
                is_signal_eligible=is_signal_eligible,
            )
        )
    return "inserted"


def _safe_int(value: Any, default: int = 1) -> int:
    try:
        number = int(float(value))
        return number if number > 0 else default
    except Exception:
        return default


def _upsert_candle(db: Session, row: dict[str, Any], *, dry_run: bool) -> str | None:
    if not row.get("trade_date") or row.get("close") is None or row.get("high") is None or row.get("low") is None:
        return None
    trade_date = date.fromisoformat(str(row["trade_date"])[:10])
    ticker = str(row.get("ticker") or "").upper().strip()
    board = str(row.get("board") or "TQBR").upper().strip()
    if not ticker:
        return None
    existing = db.scalar(
        select(Candle).where(Candle.ticker == ticker, Candle.board == board, Candle.trade_date == trade_date)
    )
    if existing:
        if not dry_run:
            existing.open = row.get("open")
            existing.high = row.get("high")
            existing.low = row.get("low")
            existing.close = row.get("close")
            existing.volume = row.get("volume")
            existing.value = row.get("value")
        return "updated"
    if not dry_run:
        db.add(
            Candle(
                ticker=ticker,
                board=board,
                trade_date=trade_date,
                open=row.get("open"),
                high=row.get("high"),
                low=row.get("low"),
                close=row.get("close"),
                volume=row.get("volume"),
                value=row.get("value"),
            )
        )
    return "inserted"


def bootstrap_moex_universe(
    db: Session,
    *,
    markets: list[str] | None = None,
    boards: list[str] | None = None,
    max_instruments: int = 500,
    include_etf: bool = True,
    include_bonds: bool = False,
    timeout_sec: float = 20.0,
    dry_run: bool = False,
) -> dict[str, Any]:
    ensure_instrument_classification_schema(db)
    settings = get_settings()
    base_url = settings.moex_base_url.rstrip("/")
    warnings: list[str] = []
    errors: list[str] = []
    fetched_items: list[dict[str, Any]] = []

    try:
        with httpx.Client(timeout=timeout_sec, follow_redirects=True) as client:
            for market, board in _security_fetch_targets(
                markets=markets,
                boards=boards,
                include_etf=include_etf,
                include_bonds=include_bonds,
            ):
                url = f"{base_url}/engines/stock/markets/{market}/boards/{board}/securities.json"
                try:
                    payload = _fetch_json(client, url, {"iss.meta": "off"})
                    fetched_items.extend(parse_moex_security_rows(payload, default_board=board, market=market))
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{market}/{board}: {exc}")
    except Exception as exc:  # noqa: BLE001
        errors.append(str(exc))

    unique: dict[str, dict[str, Any]] = {}
    for item in fetched_items:
        ticker = str(item.get("ticker") or "").upper().strip()
        if ticker and ticker not in unique:
            unique[ticker] = item
        if len(unique) >= max_instruments:
            break

    inserted = updated = skipped = 0
    asset_type_counts: dict[str, int] = {}
    for item in unique.values():
        asset_type, _eligible = classify_instrument(item)
        asset_type_counts[asset_type] = asset_type_counts.get(asset_type, 0) + 1
        result = _upsert_instrument(db, item, dry_run=dry_run)
        if result == "inserted":
            inserted += 1
        elif result == "updated":
            updated += 1
        else:
            skipped += 1

    if dry_run:
        db.rollback()
    else:
        db.commit()
    if not unique and not errors:
        warnings.append("MOEX returned no securities for requested markets/boards.")

    return {
        "ok": len(errors) == 0 or len(unique) > 0,
        "mode": "bootstrap_moex_universe",
        "dry_run": dry_run,
        "fetched": len(fetched_items),
        "unique_tickers": len(unique),
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "asset_type_counts": asset_type_counts,
        "examples": list(unique.values())[:10],
        "warnings": warnings,
        "errors": errors[:10],
    }


def _candidate_instruments(db: Session, *, tickers: list[str] | None, max_tickers: int, board: str | None) -> list[Instrument]:
    stmt = select(Instrument).where(Instrument.is_signal_eligible.is_(True)).order_by(Instrument.ticker.asc())
    if tickers:
        stmt = stmt.where(Instrument.ticker.in_(tickers))
    if board:
        stmt = stmt.where(Instrument.board == board)
    instruments = db.scalars(stmt.limit(max_tickers)).all()
    if tickers and len(instruments) < min(len(tickers), max_tickers):
        found = {item.ticker for item in instruments}
        for ticker in tickers:
            if ticker not in found:
                instruments.append(
                    SimpleNamespace(
                        ticker=ticker,
                        board=(board or "TQBR"),
                        is_signal_eligible=True,
                    )
                )
            if len(instruments) >= max_tickers:
                break
    return instruments


def bootstrap_moex_candles(
    db: Session,
    *,
    tickers: list[str] | None = None,
    max_tickers: int = 150,
    days: int = 900,
    from_date: str | None = None,
    till_date: str | None = None,
    board: str | None = None,
    timeout_sec: float = 20.0,
    sleep_sec: float = 0.15,
    dry_run: bool = False,
) -> dict[str, Any]:
    ensure_instrument_classification_schema(db)
    normalized_tickers = normalize_tickers(tickers)
    start_date, end_date = build_date_range(days=days, from_date=from_date, till_date=till_date)
    instruments = _candidate_instruments(db, tickers=normalized_tickers, max_tickers=max_tickers, board=board)
    settings = get_settings()
    base_url = settings.moex_base_url.rstrip("/")
    inserted = updated = skipped_rows = 0
    loaded_tickers: list[dict[str, Any]] = []
    skipped_tickers: list[dict[str, Any]] = []
    failed_tickers: list[dict[str, Any]] = []

    with httpx.Client(timeout=timeout_sec, follow_redirects=True) as client:
        for instrument in instruments:
            ticker = instrument.ticker.upper()
            ticker_board = (board or instrument.board or "TQBR").upper()
            url = f"{base_url}/engines/stock/markets/shares/boards/{ticker_board}/securities/{ticker}/candles.json"
            try:
                raw_rows = _fetch_paged_table(
                    client,
                    url,
                    block_name="candles",
                    params={"from": start_date, "till": end_date, "interval": 24},
                    max_rows=5000,
                )
                rows = parse_moex_history_rows({"candles": {"columns": list(raw_rows[0].keys()) if raw_rows else [], "data": [list(row.values()) for row in raw_rows]}}, ticker=ticker, board=ticker_board) if raw_rows else []
                row_inserted = row_updated = row_skipped = 0
                for row in rows:
                    result = _upsert_candle(db, row, dry_run=dry_run)
                    if result == "inserted":
                        row_inserted += 1
                    elif result == "updated":
                        row_updated += 1
                    else:
                        row_skipped += 1
                inserted += row_inserted
                updated += row_updated
                skipped_rows += row_skipped
                if rows:
                    loaded_tickers.append(
                        {
                            "ticker": ticker,
                            "board": ticker_board,
                            "rows": len(rows),
                            "inserted": row_inserted,
                            "updated": row_updated,
                            "skipped_rows": row_skipped,
                        }
                    )
                else:
                    skipped_tickers.append({"ticker": ticker, "board": ticker_board, "reason": "no_rows"})
                if dry_run:
                    db.rollback()
                else:
                    db.commit()
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                failed_tickers.append({"ticker": ticker, "board": ticker_board, "error": str(exc)})
            if sleep_sec > 0:
                time.sleep(sleep_sec)

    requested = len(instruments)
    return {
        "ok": requested > 0 and len(failed_tickers) < requested,
        "mode": "bootstrap_moex_candles",
        "dry_run": dry_run,
        "from_date": start_date,
        "till_date": end_date,
        "requested_tickers": requested,
        "loaded_tickers": len(loaded_tickers),
        "skipped_tickers": len(skipped_tickers),
        "failed_tickers": len(failed_tickers),
        "inserted_candles": inserted,
        "updated_candles": updated,
        "skipped_rows": skipped_rows,
        "loaded": loaded_tickers[:25],
        "skipped": skipped_tickers[:25],
        "failed": failed_tickers[:25],
        "warnings": ([] if instruments else ["No eligible instruments found for candle bootstrap."]),
    }


def bootstrap_market_data(
    db: Session,
    *,
    max_instruments: int = 500,
    max_tickers: int = 150,
    days: int = 900,
    include_etf: bool = True,
    include_bonds: bool = False,
    timeout_sec: float = 20.0,
    sleep_sec: float = 0.15,
    dry_run: bool = False,
) -> dict[str, Any]:
    universe = bootstrap_moex_universe(
        db,
        max_instruments=max_instruments,
        include_etf=include_etf,
        include_bonds=include_bonds,
        timeout_sec=timeout_sec,
        dry_run=dry_run,
    )
    dry_run_tickers = None
    if dry_run:
        dry_run_tickers = [str(item.get("ticker")) for item in universe.get("examples", []) if item.get("ticker")][:max_tickers]
    candles = bootstrap_moex_candles(
        db,
        tickers=dry_run_tickers,
        max_tickers=max_tickers,
        days=days,
        timeout_sec=timeout_sec,
        sleep_sec=sleep_sec,
        dry_run=dry_run,
    )
    coverage_after = None if dry_run else build_data_coverage_diagnostics(db, max_tickers=max_tickers, min_history=80, horizon=20, include_examples=False).get("summary")
    errors = [*universe.get("errors", []), *[item.get("error") for item in candles.get("failed", []) if item.get("error")]]
    warnings = [*universe.get("warnings", []), *candles.get("warnings", [])]
    return {
        "ok": bool(universe.get("ok")) and bool(candles.get("ok")),
        "mode": "bootstrap_market_data",
        "dry_run": dry_run,
        "universe": universe,
        "candles": candles,
        "coverage_after": coverage_after,
        "warnings": warnings,
        "errors": errors[:20],
    }


def build_data_bootstrap_status(db: Session) -> dict[str, Any]:
    coverage = build_data_coverage_diagnostics(db, max_tickers=500, min_history=80, horizon=20, include_examples=True)
    return {
        "ok": True,
        "mode": "data_bootstrap_status",
        "coverage": coverage.get("summary"),
        "skip_reasons": coverage.get("skip_reasons"),
        "recommendations": coverage.get("recommendations"),
        "suggested_command": "cd backend && python3 -m app.tasks.bootstrap_market_data --max-instruments 300 --max-tickers 100 --days 900",
        "dry_run_command": "cd backend && python3 -m app.tasks.bootstrap_market_data --dry-run --max-tickers 3 --days 30",
        "note": "This endpoint is read-only and does not write market data.",
    }
