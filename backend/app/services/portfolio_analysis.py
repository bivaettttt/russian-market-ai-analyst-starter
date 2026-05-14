from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import Candle
from app.services.market_briefing import SECTOR_MAP
from app.services.rss_ingestor import build_events_radar


def analyze_portfolio(db: Session, positions: list[dict[str, Any]]) -> dict[str, Any]:
    normalized, input_errors = normalize_positions(positions)

    if not normalized:
        return {
            "ok": False,
            "error": "Портфель пустой или позиции указаны некорректно.",
            "input_errors": input_errors,
        }

    rows: list[dict[str, Any]] = []
    missing_tickers: list[str] = []

    for ticker, quantity in normalized.items():
        candles = db.scalars(
            select(Candle)
            .where(Candle.ticker == ticker)
            .order_by(desc(Candle.trade_date))
            .limit(2)
        ).all()

        if not candles:
            missing_tickers.append(ticker)
            continue

        latest = candles[0]
        previous = candles[1] if len(candles) > 1 else None

        if latest.close is None:
            missing_tickers.append(ticker)
            continue

        current_value = quantity * latest.close

        previous_value = None
        daily_pnl_abs = None
        daily_pnl_pct = None

        if previous and previous.close not in (None, 0):
            previous_value = quantity * previous.close
            daily_pnl_abs = current_value - previous_value
            daily_pnl_pct = daily_pnl_abs / previous_value * 100

        rows.append(
            {
                "ticker": ticker,
                "sector": SECTOR_MAP.get(ticker, "прочее"),
                "quantity": quantity,
                "last_trade_date": latest.trade_date.isoformat(),
                "last_close": latest.close,
                "previous_close": previous.close if previous else None,
                "current_value": current_value,
                "previous_value": previous_value,
                "daily_pnl_abs": daily_pnl_abs,
                "daily_pnl_pct": daily_pnl_pct,
            }
        )

    if not rows:
        return {
            "ok": False,
            "error": "Не удалось найти рыночные данные ни по одной позиции.",
            "missing_tickers": missing_tickers,
            "input_errors": input_errors,
        }

    total_value = sum(item["current_value"] for item in rows)
    total_previous_value = sum(
        item["previous_value"] for item in rows if item["previous_value"] is not None
    )

    daily_pnl_abs = sum(
        item["daily_pnl_abs"] for item in rows if item["daily_pnl_abs"] is not None
    )

    daily_pnl_pct = None
    if total_previous_value:
        daily_pnl_pct = daily_pnl_abs / total_previous_value * 100

    latest_market_date = max(item["last_trade_date"] for item in rows)
    stale_positions = [
        item["ticker"]
        for item in rows
        if item["last_trade_date"] != latest_market_date
    ]

    for item in rows:
        item["weight_pct"] = item["current_value"] / total_value * 100 if total_value else 0
        item["current_value"] = round(item["current_value"], 2)
        item["previous_value"] = round(item["previous_value"], 2) if item["previous_value"] is not None else None
        item["daily_pnl_abs"] = round(item["daily_pnl_abs"], 2) if item["daily_pnl_abs"] is not None else None
        item["daily_pnl_pct"] = round(item["daily_pnl_pct"], 2) if item["daily_pnl_pct"] is not None else None
        item["weight_pct"] = round(item["weight_pct"], 2)

    rows = sorted(rows, key=lambda item: item["current_value"], reverse=True)

    sector_allocation = build_sector_allocation(rows=rows, total_value=total_value)
    concentration = build_concentration(rows=rows, sector_allocation=sector_allocation)
    risk_notes = build_risk_notes(
        rows=rows,
        concentration=concentration,
        missing_tickers=missing_tickers,
        stale_positions=stale_positions,
        daily_pnl_abs=daily_pnl_abs,
        daily_pnl_pct=daily_pnl_pct,
    )

    related_events = build_related_events(
        db=db,
        tickers=[item["ticker"] for item in rows],
        limit_per_ticker=3,
    )

    if related_events:
        risk_notes.append(
            "По ряду бумаг портфеля есть связанные рыночные события; их стоит учитывать вместе с ценовой динамикой."
        )

    result = {
        "ok": True,
        "date": latest_market_date,
        "total_value": round(total_value, 2),
        "daily_pnl_abs": round(daily_pnl_abs, 2),
        "daily_pnl_pct": round(daily_pnl_pct, 2) if daily_pnl_pct is not None else None,
        "positions": rows,
        "sector_allocation": sector_allocation,
        "concentration": concentration,
        "risk_notes": risk_notes,
        "related_events": related_events,
        "missing_tickers": missing_tickers,
        "stale_positions": stale_positions,
        "input_errors": input_errors,
    }

    result["summary"] = build_summary(result)

    return result


def normalize_positions(positions: list[dict[str, Any]]) -> tuple[dict[str, float], list[str]]:
    result: dict[str, float] = {}
    errors: list[str] = []

    if not isinstance(positions, list):
        return {}, ["positions должен быть списком."]

    for index, item in enumerate(positions):
        if not isinstance(item, dict):
            errors.append(f"Позиция #{index + 1}: должна быть объектом.")
            continue

        ticker = str(item.get("ticker", "")).upper().strip()

        try:
            quantity = float(item.get("quantity", 0))
        except Exception:
            errors.append(f"Позиция #{index + 1}: quantity должен быть числом.")
            continue

        if not ticker:
            errors.append(f"Позиция #{index + 1}: не указан ticker.")
            continue

        if quantity <= 0:
            errors.append(f"{ticker}: quantity должен быть больше 0.")
            continue

        result[ticker] = result.get(ticker, 0) + quantity

    return result, errors


def build_sector_allocation(rows: list[dict[str, Any]], total_value: float) -> list[dict[str, Any]]:
    sector_values: dict[str, float] = defaultdict(float)

    for item in rows:
        sector_values[item["sector"]] += item["current_value"]

    result = []
    for sector, value in sector_values.items():
        result.append(
            {
                "sector": sector,
                "value": round(value, 2),
                "weight_pct": round(value / total_value * 100, 2) if total_value else 0,
            }
        )

    return sorted(result, key=lambda item: item["weight_pct"], reverse=True)


def build_concentration(
    rows: list[dict[str, Any]],
    sector_allocation: list[dict[str, Any]],
) -> dict[str, Any]:
    weights = [item["weight_pct"] for item in rows]
    max_position = max(rows, key=lambda item: item["weight_pct"]) if rows else None
    top_3_weight = sum(item["weight_pct"] for item in rows[:3])
    hhi = sum((weight / 100) ** 2 for weight in weights)

    max_sector = sector_allocation[0] if sector_allocation else None

    if max_position and max_position["weight_pct"] >= 50:
        label = "высокая концентрация"
    elif top_3_weight >= 80:
        label = "повышенная концентрация"
    elif hhi >= 0.25:
        label = "умеренная концентрация"
    else:
        label = "диверсификация приемлемая"

    return {
        "label": label,
        "max_position": {
            "ticker": max_position["ticker"],
            "weight_pct": max_position["weight_pct"],
        } if max_position else None,
        "top_3_weight_pct": round(top_3_weight, 2),
        "hhi": round(hhi, 4),
        "max_sector": max_sector,
    }


def build_risk_notes(
    rows: list[dict[str, Any]],
    concentration: dict[str, Any],
    missing_tickers: list[str],
    stale_positions: list[str],
    daily_pnl_abs: float,
    daily_pnl_pct: float | None,
) -> list[str]:
    notes: list[str] = []

    if concentration["label"] in {"высокая концентрация", "повышенная концентрация"}:
        notes.append(
            f"Портфель имеет концентрационный риск: {concentration['label']}."
        )

    max_sector = concentration.get("max_sector")
    if max_sector and max_sector["weight_pct"] >= 60:
        notes.append(
            f"Секторная концентрация высокая: {max_sector['sector']} занимает {max_sector['weight_pct']}% портфеля."
        )

    negative_positions = [
        item for item in rows
        if item.get("daily_pnl_pct") is not None and item["daily_pnl_pct"] < 0
    ]

    if negative_positions:
        tickers = ", ".join(item["ticker"] for item in negative_positions[:5])
        notes.append(f"В минусе за последнюю сессию: {tickers}.")

    if daily_pnl_pct is not None and daily_pnl_pct < 0:
        notes.append(f"Портфель снизился за последнюю сессию на {round(daily_pnl_pct, 2)}%.")

    if missing_tickers:
        notes.append("Не найдены данные по тикерам: " + ", ".join(missing_tickers) + ".")

    if stale_positions:
        notes.append("Есть позиции с устаревшей датой торгов: " + ", ".join(stale_positions) + ".")

    if not notes:
        notes.append("Критичных рисков по текущим данным не найдено.")

    return notes


def build_summary(result: dict[str, Any]) -> str:
    parts = [
        f"Стоимость портфеля: {result['total_value']} руб.",
        f"Дневное изменение: {result['daily_pnl_abs']} руб.",
    ]

    if result["daily_pnl_pct"] is not None:
        parts.append(f"Это {result['daily_pnl_pct']}% за последнюю торговую сессию.")

    concentration = result["concentration"]
    parts.append(f"Концентрация: {concentration['label']}.")

    max_position = concentration.get("max_position")
    if max_position:
        parts.append(
            f"Крупнейшая позиция: {max_position['ticker']} — {max_position['weight_pct']}% портфеля."
        )

    max_sector = concentration.get("max_sector")
    if max_sector:
        parts.append(
            f"Крупнейший сектор: {max_sector['sector']} — {max_sector['weight_pct']}%."
        )

    if result["risk_notes"]:
        parts.append("Главный риск: " + result["risk_notes"][0])

    return " ".join(parts)



def build_related_events(
    db: Session,
    tickers: list[str],
    limit_per_ticker: int = 3,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    for ticker in tickers:
        radar = build_events_radar(
            db=db,
            limit=limit_per_ticker,
            min_importance=1,
            ticker=ticker,
        )

        events = radar.get("top_events", [])

        filtered_events = []

        for event in events:
            event_type = event.get("event_type")
            affected_assets = set(event.get("affected_assets") or [])

            if event_type in {"banking", "consumer_finance"} and ticker not in {"SBER", "VTBR"}:
                continue

            if event_type == "rates" and ticker not in {"SBER", "VTBR"}:
                continue

            if affected_assets and ticker not in affected_assets:
                continue

            filtered_events.append(event)

        if not filtered_events:
            continue

        result.append(
            {
                "ticker": ticker,
                "events_count": len(filtered_events),
                "events": [
                    {
                        "title": event.get("title"),
                        "source": event.get("source"),
                        "url": event.get("url"),
                        "importance": event.get("importance"),
                        "impact": event.get("impact"),
                        "event_type": event.get("event_type"),
                        "reasoning": event.get("reasoning"),
                    }
                    for event in filtered_events
                ],
            }
        )

    return result
