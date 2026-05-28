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


def _latest_candle_dates_by_ticker(db: Session, *, max_tickers: int = 300) -> dict[str, str | None]:
    instruments = db.scalars(
        select(Instrument)
        .where(Instrument.is_signal_eligible.is_(True))
        .order_by(Instrument.ticker.asc())
        .limit(max_tickers)
    ).all()
    tickers = [instrument.ticker for instrument in instruments]
    if not tickers:
        return {}
    rows = db.execute(
        select(Candle.ticker, func.max(Candle.trade_date))
        .where(Candle.ticker.in_(tickers))
        .group_by(Candle.ticker)
    ).all()
    latest = {str(row[0]): _date_to_str(row[1]) for row in rows}
    return {ticker: latest.get(ticker) for ticker in tickers}


def build_ticker_freshness_report(
    db: Session,
    *,
    max_tickers: int = 300,
    stale_days: int = 3,
) -> dict[str, Any]:
    latest = _latest_candle_dates_by_ticker(db, max_tickers=max_tickers)
    fresh_tickers: list[dict[str, Any]] = []
    stale_tickers: list[dict[str, Any]] = []
    missing: list[str] = []
    latest_global: str | None = None
    for ticker, latest_date in latest.items():
        if latest_date is None:
            missing.append(ticker)
            continue
        days_stale = _days_since(latest_date)
        row = {
            "ticker": ticker,
            "latest_candle_date": latest_date,
            "days_stale": days_stale,
            "status": "stale" if days_stale is None or days_stale > stale_days else "fresh",
        }
        if latest_global is None or latest_date > latest_global:
            latest_global = latest_date
        if row["status"] == "fresh":
            fresh_tickers.append(row)
        else:
            stale_tickers.append(row)
    warnings: list[str] = []
    if not latest:
        warnings.append("no_signal_eligible_tickers")
    if missing:
        warnings.append("missing_candles_tickers")
    if stale_tickers:
        warnings.append("stale_tickers")
    return {
        "ok": True,
        "mode": "ticker_freshness_report",
        "summary": {
            "tickers_checked": len(latest),
            "fresh_tickers": len(fresh_tickers),
            "stale_tickers": len(stale_tickers),
            "missing_candles_tickers": len(missing),
            "latest_candle_date": latest_global,
            "stale_days": stale_days,
        },
        "fresh_tickers": fresh_tickers,
        "stale_tickers": stale_tickers,
        "missing_candles_tickers": missing,
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


def _infer_ticker_results(
    *,
    before_latest: dict[str, str | None],
    after_latest: dict[str, str | None],
    candles: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    candles = candles or {}
    loaded = {str(row.get("ticker")): row for row in candles.get("loaded", []) if row.get("ticker")}
    failed = {str(row.get("ticker")): row for row in candles.get("failed", []) if row.get("ticker")}
    skipped = {str(row.get("ticker")): row for row in candles.get("skipped", []) if row.get("ticker")}
    tickers = sorted(set(before_latest) | set(after_latest) | set(loaded) | set(failed) | set(skipped))
    rows: list[dict[str, Any]] = []
    for ticker in tickers:
        loaded_row = loaded.get(ticker) or {}
        failed_row = failed.get(ticker)
        skipped_row = skipped.get(ticker)
        inserted = int(loaded_row.get("inserted") or 0)
        updated = int(loaded_row.get("updated") or 0)
        before_date = before_latest.get(ticker)
        after_date = after_latest.get(ticker)
        if failed_row:
            status = "failed"
        elif skipped_row and not loaded_row:
            status = "skipped"
        elif inserted > 0:
            status = "inserted"
        elif updated > 0 or (before_date != after_date and after_date is not None):
            status = "updated"
        else:
            status = "unchanged"
        rows.append(
            {
                "ticker": ticker,
                "status": status,
                "before_latest_date": before_date,
                "after_latest_date": after_date,
                "inserted": inserted,
                "updated": updated,
                "error": (failed_row or {}).get("error"),
            }
        )
    return rows


def refresh_market_data_daily(
    db: Session,
    *,
    max_instruments: int = 500,
    max_tickers: int = 150,
    days: int = 120,
    dry_run: bool = False,
    force: bool = False,
    retry_failed: bool = False,
    max_retries: int = 1,
) -> dict[str, Any]:
    before = build_market_data_freshness_status(db)
    before_summary = before.get("summary") or {}
    before_latest = _latest_candle_dates_by_ticker(db, max_tickers=max_tickers)
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
            "ticker_results": [
                {
                    "ticker": ticker,
                    "status": "planned",
                    "before_latest_date": latest_date,
                    "after_latest_date": latest_date,
                    "inserted": 0,
                    "updated": 0,
                    "error": None,
                }
                for ticker, latest_date in before_latest.items()
            ],
            "failed_tickers": [],
            "stale_tickers_after_refresh": [],
            "partial_success": False,
            "retry_attempted": False,
            "retry_count": 0,
            "recovered_tickers": [],
            "still_failed_tickers": [],
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
            "ticker_results": _infer_ticker_results(before_latest=before_latest, after_latest=before_latest, candles=None),
            "failed_tickers": [],
            "stale_tickers_after_refresh": [],
            "partial_success": False,
            "retry_attempted": False,
            "retry_count": 0,
            "recovered_tickers": [],
            "still_failed_tickers": [],
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

    retry_attempted = False
    retry_count = 0
    recovered_tickers: list[str] = []
    if retry_failed and candles and candles.get("failed") and max_retries > 0:
        failed_before_retry = [str(item.get("ticker")) for item in candles.get("failed", []) if item.get("ticker")]
        retry_attempted = True
        retry_count = 1
        try:
            retry_result = bootstrap_moex_candles(
                db,
                tickers=failed_before_retry,
                max_tickers=min(max_tickers, len(failed_before_retry)),
                days=days,
                timeout_sec=20.0,
                sleep_sec=0.15,
                dry_run=False,
            )
            recovered_tickers = [str(item.get("ticker")) for item in retry_result.get("loaded", []) if item.get("ticker")]
            if recovered_tickers:
                warnings.append("retry_recovered_some_tickers")
            remaining = [item for item in candles.get("failed", []) if str(item.get("ticker")) not in set(recovered_tickers)]
            candles["failed"] = remaining
            candles["failed_tickers"] = len(remaining)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"retry_failed: {exc}")
            warnings.append("market_data_retry_failed")

    after = build_market_data_freshness_status(db)
    after_latest = _latest_candle_dates_by_ticker(db, max_tickers=max_tickers)
    ticker_results = _infer_ticker_results(before_latest=before_latest, after_latest=after_latest, candles=candles)
    ticker_freshness_after = build_ticker_freshness_report(db, max_tickers=max_tickers)
    stale_after = ticker_freshness_after.get("stale_tickers") or []
    failed_tickers = [row for row in ticker_results if row.get("status") == "failed"]
    ok = bool(universe and universe.get("ok")) and bool(candles and candles.get("ok")) and not errors
    degraded = not ok and int((after.get("summary") or {}).get("tickers_with_candles") or 0) > 0
    partial_success = bool((candles or {}).get("loaded_tickers")) and (bool(failed_tickers) or bool(stale_after))
    recommendation = "refresh_completed" if ok and not partial_success else ("partial_refresh" if partial_success or degraded else "refresh_failed")
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
        "ticker_results": ticker_results,
        "failed_tickers": failed_tickers,
        "stale_tickers_after_refresh": stale_after,
        "partial_success": partial_success,
        "retry_attempted": retry_attempted,
        "retry_count": retry_count,
        "recovered_tickers": recovered_tickers,
        "still_failed_tickers": [row.get("ticker") for row in failed_tickers],
        "warnings": sorted(set(warnings)),
        "errors": errors[:20],
        "recommendation": recommendation,
    }
