from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Candle
from app.services.ticker_data import get_ticker_snapshot
from app.services.signal_model_registry import (
    PRODUCTION_SIGNAL_MODEL_VERSION,
    normalize_signal_model_version as registry_normalize_signal_model_version,
)

SIGNAL_MODEL_VERSION = PRODUCTION_SIGNAL_MODEL_VERSION
TECH_V2_MODEL_VERSION = "tech_v2_rsi_atr"
TECH_V3_MODEL_VERSION = "tech_v3_v1_atr_risk"
TECH_V4_MODEL_VERSION = "tech_v4_quality_rr"


ACTION_RANK = {
    "buy_watch": 1,
    "watch_buy": 2,
    "hold_watch": 3,
    "risk_sell_watch": 4,
    "no_data": 5,
    "no_price": 6,
}


def normalize_signal_model_version(model_version: str | None) -> str:
    return registry_normalize_signal_model_version(model_version)


def list_market_tickers(
    db: Session,
    limit: int = 100,
) -> list[str]:
    rows = db.execute(
        select(Candle.ticker)
        .distinct()
        .order_by(Candle.ticker)
        .limit(limit)
    ).all()

    return [str(row[0]).upper() for row in rows if row and row[0]]


def enrich_live_technical_with_range(
    technical: dict[str, Any],
    candles: list[dict[str, Any]],
    lookback: int = 20,
) -> dict[str, Any]:
    result = dict(technical or {})
    recent = candles[-lookback:] if candles else []

    highs = [
        candle.get("high")
        for candle in recent
        if candle.get("high") is not None
    ]
    lows = [
        candle.get("low")
        for candle in recent
        if candle.get("low") is not None
    ]

    if highs and result.get("recent_high") is None:
        result["recent_high"] = round(max(float(value) for value in highs), 2)

    if lows and result.get("recent_low") is None:
        result["recent_low"] = round(min(float(value) for value in lows), 2)

    return result


def build_signal_for_model(
    candles: list[dict[str, Any]],
    latest: dict[str, Any],
    technical: dict[str, Any],
    fallback_signal: dict[str, Any],
    model_version: str | None,
) -> dict[str, Any]:
    selected = normalize_signal_model_version(model_version)

    if selected == TECH_V2_MODEL_VERSION:
        try:
            from app.services.signals_backtest import build_historical_signal_v2

            candle = candles[-1] if candles else latest
            signal = build_historical_signal_v2(
                history=candles or [latest],
                candle=candle,
                technical=technical,
            )
            signal["model_version"] = TECH_V2_MODEL_VERSION
            return signal
        except Exception as exc:
            signal = dict(fallback_signal or {})
            signal["model_version"] = SIGNAL_MODEL_VERSION
            signal["fallback_error"] = str(exc)
            return signal

    if selected == TECH_V3_MODEL_VERSION:
        try:
            from app.services.signals_backtest import build_historical_signal_v3

            candle = candles[-1] if candles else latest
            signal = build_historical_signal_v3(
                history=candles or [latest],
                candle=candle,
                technical=technical,
            )
            signal["model_version"] = TECH_V3_MODEL_VERSION
            return signal
        except Exception as exc:
            signal = dict(fallback_signal or {})
            signal["model_version"] = SIGNAL_MODEL_VERSION
            signal["fallback_error"] = str(exc)
            return signal

    if selected == TECH_V4_MODEL_VERSION:
        try:
            from app.services.signals_backtest import build_historical_signal_v4

            candle = candles[-1] if candles else latest
            signal = build_historical_signal_v4(
                history=candles or [latest],
                candle=candle,
                technical=technical,
            )
            signal["model_version"] = TECH_V4_MODEL_VERSION
            return signal
        except Exception as exc:
            signal = dict(fallback_signal or {})
            signal["model_version"] = SIGNAL_MODEL_VERSION
            signal["fallback_error"] = str(exc)
            return signal

    signal = dict(fallback_signal or {})
    signal["model_version"] = SIGNAL_MODEL_VERSION
    return signal


def build_signal_row(
    db: Session,
    ticker: str,
    candles_limit: int = 120,
    model_version: str | None = None,
) -> dict[str, Any]:
    selected_model_version = normalize_signal_model_version(model_version)

    snapshot = get_ticker_snapshot(
        db=db,
        ticker=ticker,
        limit=candles_limit,
    )

    latest = snapshot.get("latest") or {}
    raw_technical = snapshot.get("technical") or {}
    fallback_signal = snapshot.get("signal") or {}
    instrument = snapshot.get("instrument") or {}
    candles = snapshot.get("candles") or []

    technical = enrich_live_technical_with_range(
        technical=raw_technical,
        candles=candles,
    )

    signal = build_signal_for_model(
        candles=candles,
        latest=latest,
        technical=technical,
        fallback_signal=fallback_signal,
        model_version=selected_model_version,
    )

    actual_model_version = signal.get("model_version") or selected_model_version

    return {
        "ticker": ticker,
        "name": instrument.get("name") or ticker,
        "sector": instrument.get("sector"),
        "price": latest.get("close"),
        "change_pct": latest.get("change_pct"),
        "trade_date": latest.get("trade_date"),
        "signal": signal,
        "technical": {
            "trend": technical.get("trend"),
            "sma_20": technical.get("sma_20"),
            "sma_50": technical.get("sma_50"),
            "return_5d_pct": technical.get("return_5d_pct"),
            "volatility_20d_pct": technical.get("volatility_20d_pct"),
            "volume_ratio": technical.get("volume_ratio"),
            "recent_high": technical.get("recent_high"),
            "recent_low": technical.get("recent_low"),
        },
        "model_version": actual_model_version,
        "ticker_url": f"/tickers/{ticker}",
    }


def list_market_signals(
    db: Session,
    limit: int = 100,
    candles_limit: int = 120,
    action: str | None = None,
    model_version: str | None = None,
) -> dict[str, Any]:
    selected_model_version = normalize_signal_model_version(model_version)

    tickers = list_market_tickers(
        db=db,
        limit=limit,
    )

    rows = [
        build_signal_row(
            db=db,
            ticker=ticker,
            candles_limit=candles_limit,
            model_version=selected_model_version,
        )
        for ticker in tickers
    ]

    if action:
        rows = [
            row for row in rows
            if (row.get("signal") or {}).get("action") == action
        ]

    rows.sort(
        key=lambda row: (
            ACTION_RANK.get((row.get("signal") or {}).get("action"), 99),
            -float((row.get("signal") or {}).get("confidence_pct") or 0),
            row.get("ticker") or "",
        )
    )

    summary = {
        "total": len(rows),
        "buy_watch": sum(1 for row in rows if (row.get("signal") or {}).get("action") == "buy_watch"),
        "watch_buy": sum(1 for row in rows if (row.get("signal") or {}).get("action") == "watch_buy"),
        "hold_watch": sum(1 for row in rows if (row.get("signal") or {}).get("action") == "hold_watch"),
        "risk_sell_watch": sum(1 for row in rows if (row.get("signal") or {}).get("action") == "risk_sell_watch"),
    }

    return {
        "model_version": selected_model_version,
        "summary": summary,
        "rows": rows,
    }
