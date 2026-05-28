from __future__ import annotations

import csv
import io
from typing import Any

from sqlalchemy.orm import Session

from app.services.data_coverage_diagnostics import build_data_coverage_diagnostics
from app.services.market_data_refresh import build_market_data_freshness_status, build_ticker_freshness_report


def _csv_text(headers: list[str], rows: list[dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key) for key in headers})
    return output.getvalue()


def build_market_refresh_report(
    db: Session,
    *,
    stale_days: int = 3,
    max_tickers: int = 300,
) -> dict[str, Any]:
    freshness = build_market_data_freshness_status(db, stale_days=stale_days)
    ticker_freshness = build_ticker_freshness_report(db, max_tickers=max_tickers, stale_days=stale_days)
    coverage = build_data_coverage_diagnostics(db, max_tickers=max_tickers, min_history=80, horizon=20, include_examples=False)
    freshness_summary = freshness.get("summary") or {}
    ticker_summary = ticker_freshness.get("summary") or {}
    coverage_summary = coverage.get("summary") or {}
    if int(freshness_summary.get("tickers_with_candles") or 0) <= 0:
        recommended_action = "bootstrap_required"
    elif freshness_summary.get("is_stale"):
        recommended_action = "refresh_market_data"
    else:
        recommended_action = "continue_tracking"
    warnings = sorted(
        set(
            (freshness.get("warnings") or [])
            + (ticker_freshness.get("warnings") or [])
            + (coverage.get("warnings") or [])
        )
    )
    return {
        "ok": True,
        "mode": "market_refresh_report",
        "summary": {
            "latest_candle_date": freshness_summary.get("latest_candle_date"),
            "days_since_latest_candle": freshness_summary.get("days_since_latest_candle"),
            "market_data_stale": freshness_summary.get("is_stale"),
            "tickers_checked": ticker_summary.get("tickers_checked", 0),
            "fresh_tickers": ticker_summary.get("fresh_tickers", 0),
            "stale_tickers": ticker_summary.get("stale_tickers", 0),
            "missing_candles_tickers": ticker_summary.get("missing_candles_tickers", 0),
            "coverage_level": coverage_summary.get("coverage_level"),
            "recommended_action": recommended_action,
        },
        "ticker_freshness": ticker_freshness,
        "data_coverage": coverage.get("summary"),
        "warnings": warnings,
    }


def build_market_refresh_notification(
    db: Session,
    *,
    stale_days: int = 3,
) -> dict[str, Any]:
    report = build_market_refresh_report(db, stale_days=stale_days, max_tickers=300)
    summary = report.get("summary") or {}
    latest = summary.get("latest_candle_date")
    if not latest:
        status = "critical"
        message = "No candle data found. Run bootstrap_market_data first."
    elif summary.get("market_data_stale"):
        status = "warning"
        days = summary.get("days_since_latest_candle")
        days_text = f" by {days} days" if days is not None else ""
        message = f"Market data is stale{days_text}. Run refresh before creating paper snapshot."
    else:
        status = "ok"
        message = f"Market data is fresh. Latest candle: {latest}."
    return {
        "ok": True,
        "mode": "market_refresh_notification",
        "status": status,
        "message": message,
        "recommended_action": summary.get("recommended_action"),
        "metrics": summary,
        "warnings": report.get("warnings") or [],
    }


def build_market_refresh_report_csv(
    db: Session,
    *,
    stale_days: int = 3,
    max_tickers: int = 300,
) -> str:
    report = build_market_refresh_report(db, stale_days=stale_days, max_tickers=max_tickers)
    rows: list[dict[str, Any]] = []
    ticker_freshness = report.get("ticker_freshness") or {}
    for row in ticker_freshness.get("fresh_tickers") or []:
        rows.append(row)
    for row in ticker_freshness.get("stale_tickers") or []:
        rows.append(row)
    for ticker in ticker_freshness.get("missing_candles_tickers") or []:
        rows.append(
            {
                "ticker": ticker,
                "latest_candle_date": None,
                "days_stale": None,
                "status": "missing_candles",
            }
        )
    rows = sorted(rows, key=lambda row: (str(row.get("status") or ""), str(row.get("ticker") or "")))
    return _csv_text(["ticker", "latest_candle_date", "days_stale", "status"], rows)
