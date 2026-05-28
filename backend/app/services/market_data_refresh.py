from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Candle, Instrument
from app.services.consumer_signals import _round
from app.services.data_coverage_diagnostics import build_data_coverage_diagnostics
from app.services.moex_data_bootstrap import bootstrap_moex_candles, bootstrap_moex_universe


def _date_to_str(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else value


def _days_since(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value[:10])
        except ValueError:
            return None
    if not isinstance(value, date):
        return None
    return (date.today() - value).days


def _freshness_recommendation(
    *,
    tickers_with_candles: int,
    total_instruments: int,
    is_stale: bool,
) -> str:
    if tickers_with_candles <= 0:
        return "bootstrap_required" if total_instruments <= 0 else "refresh_market_data"
    if is_stale:
        return "refresh_market_data"
    return "fresh"


def build_market_data_freshness_status(
    db: Session,
    *,
    stale_days: int = 3,
) -> dict[str, Any]:
    row = db.execute(
        select(
            func.count(Candle.id),
            func.count(func.distinct(Candle.ticker)),
            func.max(Candle.trade_date),
        )
    ).one()
    total_candles = int(row[0] or 0)
    tickers_with_candles = int(row[1] or 0)
    latest_candle_date = row[2]
    total_instruments = int(db.scalar(select(func.count(Instrument.id))) or 0)
    days_since_latest = _days_since(latest_candle_date)
    is_stale = days_since_latest is None or days_since_latest > stale_days
    coverage_level = "empty"
    warnings: list[str] = []
    try:
        coverage = build_data_coverage_diagnostics(db, max_tickers=500, min_history=80, horizon=20, include_examples=False)
        coverage_level = str((coverage.get("summary") or {}).get("coverage_level") or "empty")
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"coverage_diagnostics_failed: {exc}")

    recommendation = _freshness_recommendation(
        tickers_with_candles=tickers_with_candles,
        total_instruments=total_instruments,
        is_stale=is_stale,
    )
    if total_candles <= 0:
        warnings.append("no_market_candles")
    if is_stale:
        warnings.append("stale_market_data")
    if total_instruments <= 0:
        warnings.append("no_instruments")

    return {
        "ok": True,
        "mode": "market_data_freshness_status",
        "summary": {
            "total_instruments": total_instruments,
            "total_candles": total_candles,
            "tickers_with_candles": tickers_with_candles,
            "latest_candle_date": _date_to_str(latest_candle_date),
            "days_since_latest_candle": days_since_latest,
            "stale_days": stale_days,
            "is_stale": bool(is_stale),
            "coverage_level": coverage_level,
            "recommendation": recommendation,
        },
        "warnings": warnings,
    }


def _summarize_refresh(universe: dict[str, Any] | None, candles: dict[str, Any] | None) -> dict[str, Any]:
    universe = universe or {}
    candles = candles or {}
    return {
        "instruments_loaded": int(universe.get("unique_tickers") or 0),
        "instruments_inserted": int(universe.get("inserted") or 0),
        "instruments_updated": int(universe.get("updated") or 0),
        "candles_loaded_tickers": int(candles.get("loaded_tickers") or 0),
        "inserted": int(candles.get("inserted_candles") or 0),
        "updated": int(candles.get("updated_candles") or 0),
        "skipped": int(candles.get("skipped_tickers") or 0) + int(candles.get("skipped_rows") or 0),
        "failed_tickers": int(candles.get("failed_tickers") or 0),
    }


def refresh_market_data_daily(
    db: Session,
    *,
    max_instruments: int = 500,
    max_tickers: int = 150,
    days: int = 120,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    before = build_market_data_freshness_status(db)
    before_summary = before.get("summary") or {}
    warnings = list(before.get("warnings") or [])
    if dry_run:
        return {
            "ok": True,
            "mode": "market_data_daily_refresh",
            "dry_run": True,
            "force": force,
            "before": before,
            "after": before,
            "refresh_result": {
                "planned": True,
                "max_instruments": max_instruments,
                "max_tickers": max_tickers,
                "days": days,
                "would_refresh": bool(force or before_summary.get("is_stale") or before_summary.get("tickers_with_candles", 0) <= 0),
            },
            "warnings": warnings,
            "recommendation": "dry_run_only",
        }

    if not force and not bool(before_summary.get("is_stale")) and int(before_summary.get("tickers_with_candles") or 0) > 0:
        return {
            "ok": True,
            "mode": "market_data_daily_refresh",
            "dry_run": False,
            "force": False,
            "before": before,
            "after": before,
            "refresh_result": {"skipped_reason": "market_data_already_fresh"},
            "warnings": warnings,
            "recommendation": "market_data_fresh",
        }

    universe: dict[str, Any] | None = None
    candles: dict[str, Any] | None = None
    errors: list[str] = []
    try:
        universe = bootstrap_moex_universe(
            db,
            max_instruments=max_instruments,
            include_etf=True,
            include_bonds=False,
            timeout_sec=20.0,
            dry_run=False,
        )
        candles = bootstrap_moex_candles(
            db,
            max_tickers=max_tickers,
            days=days,
            timeout_sec=20.0,
            sleep_sec=0.15,
            dry_run=False,
        )
        errors.extend(str(item) for item in universe.get("errors", []) if item)
        errors.extend(str(item.get("error")) for item in candles.get("failed", []) if item.get("error"))
    except Exception as exc:  # noqa: BLE001
        errors.append(str(exc))
        warnings.append("market_data_refresh_failed")

    after = build_market_data_freshness_status(db)
    ok = bool(universe and universe.get("ok")) and bool(candles and candles.get("ok")) and not errors
    degraded = not ok and int((after.get("summary") or {}).get("tickers_with_candles") or 0) > 0
    recommendation = "refresh_completed" if ok else ("market_data_fresh" if degraded else "refresh_failed")
    if not ok:
        warnings.append("market_data_refresh_failed")
    return {
        "ok": bool(ok or degraded),
        "degraded": bool(degraded and not ok),
        "mode": "market_data_daily_refresh",
        "dry_run": False,
        "force": force,
        "before": before,
        "after": after,
        "refresh_result": _summarize_refresh(universe, candles),
        "warnings": sorted(set(warnings)),
        "errors": errors[:20],
        "recommendation": recommendation,
    }
