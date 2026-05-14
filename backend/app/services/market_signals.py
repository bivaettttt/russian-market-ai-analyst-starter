from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import Candle
from app.services.market_radar import build_market_radar
from app.services.market_briefing import SECTOR_MAP


def build_market_signals(
    db: Session,
    price_threshold_pct: float = 2.0,
    volume_spike_ratio: float = 2.0,
    min_value_rub: float = 10_000_000,
) -> dict[str, Any]:
    radar = build_market_radar(db=db, limit=50)
    latest_date = radar.get("latest_date")

    signals: list[dict[str, Any]] = []

    if not latest_date:
        return {
            "date": None,
            "signals_count": 0,
            "signals": [],
            "summary": "Нет данных для построения рыночных сигналов.",
            "data_quality": radar.get("stale_tickers", []),
        }

    tickers = db.scalars(select(Candle.ticker).distinct().order_by(Candle.ticker)).all()

    current_moves: list[dict[str, Any]] = []

    for ticker in tickers:
        candles = db.scalars(
            select(Candle)
            .where(Candle.ticker == ticker)
            .order_by(desc(Candle.trade_date))
            .limit(25)
        ).all()

        if len(candles) < 2:
            continue

        latest = candles[0]
        previous = candles[1]

        if latest.trade_date.isoformat() != latest_date:
            continue

        if latest.close is None or previous.close in (None, 0):
            continue

        change_abs = latest.close - previous.close
        change_pct = (change_abs / previous.close) * 100

        history_for_avg = candles[1:21]
        values = [item.value or 0 for item in history_for_avg if item.value is not None]
        avg_value_20d = sum(values) / len(values) if values else 0
        value_ratio = (latest.value or 0) / avg_value_20d if avg_value_20d > 0 else None

        move = {
            "ticker": ticker,
            "sector": SECTOR_MAP.get(ticker, "прочее"),
            "trade_date": latest.trade_date.isoformat(),
            "close": latest.close,
            "previous_close": previous.close,
            "change_abs": round(change_abs, 4),
            "change_pct": round(change_pct, 2),
            "value": latest.value,
            "avg_value_20d": round(avg_value_20d, 2),
            "value_ratio": round(value_ratio, 2) if value_ratio is not None else None,
        }
        current_moves.append(move)

        if change_pct >= price_threshold_pct:
            signals.append(
                {
                    "type": "price_jump",
                    "severity": "high" if change_pct >= price_threshold_pct * 2 else "medium",
                    "ticker": ticker,
                    "sector": move["sector"],
                    "title": f"{ticker}: сильный рост цены",
                    "description": f"{ticker} вырос на {change_pct:.2f}% за последнюю торговую сессию.",
                    "metrics": move,
                }
            )

        if change_pct <= -price_threshold_pct:
            signals.append(
                {
                    "type": "price_drop",
                    "severity": "high" if change_pct <= -price_threshold_pct * 2 else "medium",
                    "ticker": ticker,
                    "sector": move["sector"],
                    "title": f"{ticker}: сильное снижение цены",
                    "description": f"{ticker} снизился на {change_pct:.2f}% за последнюю торговую сессию.",
                    "metrics": move,
                }
            )

        if (
            value_ratio is not None
            and value_ratio >= volume_spike_ratio
            and (latest.value or 0) >= min_value_rub
        ):
            signals.append(
                {
                    "type": "volume_spike",
                    "severity": "medium" if value_ratio < volume_spike_ratio * 2 else "high",
                    "ticker": ticker,
                    "sector": move["sector"],
                    "title": f"{ticker}: всплеск оборота",
                    "description": (
                        f"Оборот по {ticker} выше среднего за 20 сессий примерно в {value_ratio:.2f} раза."
                    ),
                    "metrics": move,
                }
            )

    sector_signals = build_sector_signals(current_moves=current_moves)
    signals.extend(sector_signals)

    stale_tickers = radar.get("stale_tickers", [])
    if stale_tickers:
        signals.append(
            {
                "type": "data_quality",
                "severity": "low",
                "ticker": None,
                "sector": None,
                "title": "Есть устаревшие тикеры",
                "description": "Часть бумаг исключена из анализа, потому что последняя дата торгов отличается от основной даты рынка.",
                "metrics": {
                    "stale_tickers": stale_tickers,
                },
            }
        )

    if not signals:
        signals.append(
            {
                "type": "quiet_market",
                "severity": "info",
                "ticker": None,
                "sector": None,
                "title": "Сильных рыночных сигналов не найдено",
                "description": "По заданным порогам нет резких движений цены или всплесков оборота.",
                "metrics": {
                    "price_threshold_pct": price_threshold_pct,
                    "volume_spike_ratio": volume_spike_ratio,
                    "min_value_rub": min_value_rub,
                },
            }
        )

    severity_rank = {"high": 0, "medium": 1, "low": 2, "info": 3}
    signals = sorted(signals, key=lambda item: severity_rank.get(item["severity"], 99))

    return {
        "date": latest_date,
        "signals_count": len(signals),
        "signals": signals,
        "summary": build_signals_summary(signals),
        "parameters": {
            "price_threshold_pct": price_threshold_pct,
            "volume_spike_ratio": volume_spike_ratio,
            "min_value_rub": min_value_rub,
        },
        "data_quality": {
            "stale_tickers_count": len(stale_tickers),
            "stale_tickers": stale_tickers,
        },
    }


def build_sector_signals(current_moves: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sector_values: dict[str, list[float]] = defaultdict(list)

    for move in current_moves:
        sector_values[move["sector"]].append(float(move["change_pct"]))

    result: list[dict[str, Any]] = []

    for sector, values in sector_values.items():
        if len(values) < 2:
            continue

        avg_change = sum(values) / len(values)

        if avg_change >= 0.5:
            result.append(
                {
                    "type": "sector_strength",
                    "severity": "medium",
                    "ticker": None,
                    "sector": sector,
                    "title": f"Сектор выглядит сильнее рынка: {sector}",
                    "description": f"Среднее изменение бумаг сектора: {avg_change:.2f}%.",
                    "metrics": {
                        "sector": sector,
                        "avg_change_pct": round(avg_change, 2),
                        "sample_size": len(values),
                    },
                }
            )

        if avg_change <= -0.5:
            result.append(
                {
                    "type": "sector_weakness",
                    "severity": "medium",
                    "ticker": None,
                    "sector": sector,
                    "title": f"Сектор под давлением: {sector}",
                    "description": f"Среднее изменение бумаг сектора: {avg_change:.2f}%.",
                    "metrics": {
                        "sector": sector,
                        "avg_change_pct": round(avg_change, 2),
                        "sample_size": len(values),
                    },
                }
            )

    return result


def build_signals_summary(signals: list[dict[str, Any]]) -> str:
    high = [item for item in signals if item["severity"] == "high"]
    medium = [item for item in signals if item["severity"] == "medium"]

    if high:
        titles = "; ".join(item["title"] for item in high[:3])
        return f"Найдены сильные сигналы: {titles}."

    if medium:
        titles = "; ".join(item["title"] for item in medium[:3])
        return f"Найдены умеренные сигналы: {titles}."

    return signals[0]["description"] if signals else "Сигналов нет."
