from __future__ import annotations

import math
from statistics import mean, stdev
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import Candle
from app.services.market_briefing import SECTOR_MAP


def build_ticker_analysis(db: Session, ticker: str) -> dict[str, Any]:
    ticker = ticker.upper().strip()

    candles = db.scalars(
        select(Candle)
        .where(Candle.ticker == ticker)
        .order_by(desc(Candle.trade_date))
        .limit(120)
    ).all()

    if not candles:
        return {
            "ticker": ticker,
            "found": False,
            "error": "Нет данных по тикеру.",
        }

    candles = list(candles)
    latest = candles[0]

    result = {
        "ticker": ticker,
        "found": True,
        "board": latest.board,
        "sector": SECTOR_MAP.get(ticker, "прочее"),
        "last_trade_date": latest.trade_date.isoformat(),
        "last_close": latest.close,
        "volume": latest.volume,
        "value": latest.value,
        "performance": build_performance(candles),
        "liquidity": build_liquidity(candles),
        "risk": build_risk(candles),
    }

    result["summary"] = build_summary(result)

    return result


def build_performance(candles: list[Candle]) -> dict[str, Any]:
    latest = candles[0]

    def change_from_sessions_back(n: int) -> dict[str, Any] | None:
        if len(candles) <= n:
            return None

        past = candles[n]

        if latest.close is None or past.close in (None, 0):
            return None

        change_abs = latest.close - past.close
        change_pct = change_abs / past.close * 100

        return {
            "sessions": n,
            "from_date": past.trade_date.isoformat(),
            "to_date": latest.trade_date.isoformat(),
            "start_close": past.close,
            "end_close": latest.close,
            "change_abs": round(change_abs, 4),
            "change_pct": round(change_pct, 2),
        }

    return {
        "1_session": change_from_sessions_back(1),
        "5_sessions": change_from_sessions_back(5),
        "20_sessions": change_from_sessions_back(20),
        "60_sessions": change_from_sessions_back(60),
    }


def build_liquidity(candles: list[Candle]) -> dict[str, Any]:
    latest = candles[0]

    last_20 = candles[:20]
    values = [item.value or 0 for item in last_20 if item.value is not None]
    volumes = [item.volume or 0 for item in last_20 if item.volume is not None]

    avg_value_20 = mean(values) if values else 0
    avg_volume_20 = mean(volumes) if volumes else 0

    value_ratio = None
    if avg_value_20 > 0 and latest.value is not None:
        value_ratio = latest.value / avg_value_20

    return {
        "last_value": latest.value,
        "avg_value_20_sessions": round(avg_value_20, 2),
        "last_volume": latest.volume,
        "avg_volume_20_sessions": round(avg_volume_20, 2),
        "value_to_avg_20_ratio": round(value_ratio, 2) if value_ratio is not None else None,
        "liquidity_label": classify_liquidity(avg_value_20),
    }


def build_risk(candles: list[Candle]) -> dict[str, Any]:
    returns = []

    max_items = min(len(candles) - 1, 20)

    for i in range(max_items):
        current = candles[i]
        previous = candles[i + 1]

        if current.close is None or previous.close in (None, 0):
            continue

        returns.append((current.close / previous.close - 1) * 100)

    if len(returns) >= 2:
        volatility_20 = stdev(returns)
    else:
        volatility_20 = 0

    latest_change = returns[0] if returns else 0

    risk_level = classify_risk(volatility_20=volatility_20, latest_change=latest_change)

    return {
        "daily_change_pct": round(latest_change, 2),
        "volatility_20_sessions_pct": round(volatility_20, 2),
        "risk_level": risk_level,
    }


def classify_liquidity(avg_value_20: float) -> str:
    if avg_value_20 >= 1_000_000_000:
        return "высокая ликвидность"
    if avg_value_20 >= 100_000_000:
        return "средняя ликвидность"
    if avg_value_20 >= 10_000_000:
        return "низкая ликвидность"

    return "очень низкая ликвидность"


def classify_risk(volatility_20: float, latest_change: float) -> str:
    if abs(latest_change) >= 5 or volatility_20 >= 4:
        return "повышенный риск"
    if abs(latest_change) >= 2 or volatility_20 >= 2:
        return "умеренный риск"

    return "низкий краткосрочный риск"


def build_summary(result: dict[str, Any]) -> str:
    ticker = result["ticker"]
    sector = result["sector"]
    last_close = result["last_close"]
    date = result["last_trade_date"]

    perf_1 = result["performance"].get("1_session")
    perf_20 = result["performance"].get("20_sessions")
    liquidity = result["liquidity"]
    risk = result["risk"]

    parts = [
        f"{ticker}: сектор — {sector}.",
        f"Последняя цена на {date}: {last_close}.",
    ]

    if perf_1:
        parts.append(f"За последнюю сессию изменение: {perf_1['change_pct']}%.")

    if perf_20:
        parts.append(f"За 20 сессий изменение: {perf_20['change_pct']}%.")

    parts.append(f"Ликвидность: {liquidity['liquidity_label']}.")

    parts.append(
        f"Риск-статус: {risk['risk_level']}; волатильность за 20 сессий около {risk['volatility_20_sessions_pct']}%."
    )

    return " ".join(parts)
