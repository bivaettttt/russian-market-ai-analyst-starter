from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.market_briefing import build_market_briefing
from app.services.market_signals import build_market_signals


def build_market_daily_report(
    db: Session,
    limit: int = 5,
    price_threshold_pct: float = 1.5,
    volume_spike_ratio: float = 2.0,
    min_value_rub: float = 10_000_000,
) -> dict[str, Any]:
    briefing = build_market_briefing(db=db, limit=limit)
    signals = build_market_signals(
        db=db,
        price_threshold_pct=price_threshold_pct,
        volume_spike_ratio=volume_spike_ratio,
        min_value_rub=min_value_rub,
    )

    risk_notes = build_risk_notes(briefing=briefing, signals=signals)
    watchlist = build_watchlist(briefing=briefing, signals=signals)

    return {
        "date": briefing.get("date"),
        "market": briefing.get("market"),
        "market_mood": briefing.get("market_mood"),
        "executive_summary": build_executive_summary(
            briefing=briefing,
            signals=signals,
            risk_notes=risk_notes,
        ),
        "briefing": briefing,
        "signals": signals,
        "risk_notes": risk_notes,
        "watchlist": watchlist,
        "disclaimer": "Это аналитическая сводка на основе рыночных данных, а не инвестиционная рекомендация.",
    }


def build_executive_summary(
    briefing: dict[str, Any],
    signals: dict[str, Any],
    risk_notes: list[str],
) -> str:
    date = briefing.get("date")
    mood = briefing.get("market_mood")
    breadth = briefing.get("breadth", {})
    top_gainers = briefing.get("top_gainers", [])
    top_losers = briefing.get("top_losers", [])
    most_traded = briefing.get("most_traded_by_value", [])
    sector_heat = briefing.get("sector_heat", [])

    parts = [
        f"Ежедневный отчёт по рынку РФ на {date}.",
        f"Фон: {mood}.",
        f"Рыночная ширина: растут {breadth.get('up', 0)}, снижаются {breadth.get('down', 0)}, без изменений {breadth.get('flat', 0)}.",
    ]

    if top_gainers:
        leader = top_gainers[0]
        parts.append(f"Лидер роста: {leader['ticker']} ({leader['change_pct']}%).")

    if top_losers:
        laggard = top_losers[0]
        parts.append(f"Лидер снижения: {laggard['ticker']} ({laggard['change_pct']}%).")

    if most_traded:
        traded = most_traded[0]
        value_bln = round((traded.get("value") or 0) / 1_000_000_000, 2)
        parts.append(f"Максимальный оборот: {traded['ticker']} — около {value_bln} млрд руб.")

    if sector_heat:
        sector = sector_heat[0]
        parts.append(f"Сильнейший сектор в выборке: {sector['sector']}.")

    signal_items = [
        item for item in signals.get("signals", [])
        if item.get("type") not in {"data_quality", "quiet_market"}
    ]

    if signal_items:
        titles = "; ".join(item["title"] for item in signal_items[:3])
        parts.append(f"Сигналы: {titles}.")
    else:
        parts.append("Сильных ценовых или объёмных сигналов по текущим порогам нет.")

    if risk_notes:
        parts.append(f"Главный риск: {risk_notes[0]}")

    return " ".join(part for part in parts if part)


def build_risk_notes(
    briefing: dict[str, Any],
    signals: dict[str, Any],
) -> list[str]:
    notes: list[str] = []

    breadth = briefing.get("breadth", {})
    up = breadth.get("up", 0)
    down = breadth.get("down", 0)

    if up > down and down > 0:
        notes.append(
            "Рост рынка не является полностью однородным: часть бумаг снижается, поэтому важно смотреть не только на общий фон."
        )

    if briefing.get("data_quality", {}).get("stale_tickers_count", 0) > 0:
        notes.append(
            "В базе есть бумаги с устаревшими датами торгов; такие тикеры нельзя смешивать с текущей сессией."
        )

    signal_items = signals.get("signals", [])
    volume_signals = [item for item in signal_items if item.get("type") == "volume_spike"]
    price_drop_signals = [item for item in signal_items if item.get("type") == "price_drop"]

    if volume_signals:
        notes.append(
            "Есть всплески оборота: по таким бумагам стоит проверить новости, раскрытия и корпоративные события."
        )

    if price_drop_signals:
        tickers = ", ".join(item["ticker"] for item in price_drop_signals if item.get("ticker"))
        if tickers:
            notes.append(f"Под давлением находятся: {tickers}.")

    if not notes:
        notes.append(
            "Существенных рыночных рисков по текущим порогам не найдено."
        )

    return notes


def build_watchlist(
    briefing: dict[str, Any],
    signals: dict[str, Any],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    seen: set[str] = set()

    for item in signals.get("signals", []):
        ticker = item.get("ticker")
        if not ticker or ticker in seen:
            continue

        result.append(
            {
                "ticker": ticker,
                "reason": item.get("title"),
                "signal_type": item.get("type"),
                "severity": item.get("severity"),
            }
        )
        seen.add(ticker)

    for item in briefing.get("most_traded_by_value", [])[:3]:
        ticker = item.get("ticker")
        if not ticker or ticker in seen:
            continue

        result.append(
            {
                "ticker": ticker,
                "reason": "Высокий оборот относительно остальных бумаг в текущей выборке.",
                "signal_type": "liquidity_focus",
                "severity": "info",
            }
        )
        seen.add(ticker)

    return result[:10]
