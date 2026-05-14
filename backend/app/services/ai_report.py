from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.market_daily_report import build_market_daily_report
from app.services.rss_ingestor import build_events_radar
from app.services.portfolio_analysis import analyze_portfolio


DEFAULT_DEMO_PORTFOLIO = [
    {"ticker": "SBER", "quantity": 10},
    {"ticker": "LKOH", "quantity": 1},
    {"ticker": "GAZP", "quantity": 50},
    {"ticker": "PLZL", "quantity": 1},
]


def build_ai_report(
    db: Session,
    positions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if positions is None:
        positions = DEFAULT_DEMO_PORTFOLIO

    market = build_market_daily_report(
        db=db,
        limit=5,
        price_threshold_pct=1.5,
        volume_spike_ratio=2.0,
        min_value_rub=10_000_000,
    )

    events = build_events_radar(
        db=db,
        limit=5,
        min_importance=7,
    )

    portfolio = analyze_portfolio(
        db=db,
        positions=positions,
    )

    sections = {
        "market_context": build_market_context(market),
        "important_events": build_events_context(events),
        "market_signals": build_signals_context(market),
        "portfolio_context": build_portfolio_context(portfolio),
        "risk_review": build_risk_review(market=market, portfolio=portfolio),
        "watchlist": build_watchlist_context(market=market, portfolio=portfolio),
        "conclusion": build_conclusion(market=market, events=events, portfolio=portfolio),
    }

    return {
        "date": market.get("date"),
        "title": "AI Report российского рынка",
        "market": market,
        "events": events,
        "portfolio": portfolio,
        "sections": sections,
        "full_report": build_full_report(sections),
        "disclaimer": "Это аналитическая сводка на основе рыночных и новостных данных, а не инвестиционная рекомендация.",
    }


def build_market_context(market: dict[str, Any]) -> str:
    date = market.get("date")
    mood = market.get("market_mood")
    briefing = market.get("briefing", {})
    breadth = briefing.get("breadth", {})

    top_gainers = briefing.get("top_gainers", [])
    top_losers = briefing.get("top_losers", [])
    most_traded = briefing.get("most_traded_by_value", [])

    parts = [
        f"Рыночный фон на {date}: {mood}.",
        f"Рыночная ширина: растут {breadth.get('up', 0)}, снижаются {breadth.get('down', 0)}, без изменений {breadth.get('flat', 0)}.",
    ]

    if top_gainers:
        item = top_gainers[0]
        parts.append(f"Лидер роста: {item['ticker']} ({item['change_pct']}%).")

    if top_losers:
        item = top_losers[0]
        parts.append(f"Лидер снижения: {item['ticker']} ({item['change_pct']}%).")

    if most_traded:
        item = most_traded[0]
        value_bln = round((item.get("value") or 0) / 1_000_000_000, 2)
        parts.append(f"Наибольший оборот в выборке у {item['ticker']}: около {value_bln} млрд руб.")

    return " ".join(parts)





def build_events_context(events: dict[str, Any]) -> str:
    top_events = events.get("top_events", [])

    if not top_events:
        return "Значимых событий по текущим фильтрам не найдено."

    lines = []

    for index, event in enumerate(top_events[:5], start=1):
        title = event.get("title") or "Без заголовка"
        event_type = event.get("event_type") or "other"
        importance = event.get("importance")
        impact = event.get("impact") or "uncertain"
        reasoning = event.get("reasoning") or ""

        lines.append(
            f"{index}. {title}\n"
            f"   Тип: {event_type}. Важность: {importance}/10. Влияние: {impact}.\n"
            f"   Смысл: {reasoning}"
        )

    return "\n\n".join(lines)

def build_signals_context(market: dict[str, Any]) -> str:
    signals = market.get("signals", {})
    items = signals.get("signals", [])

    meaningful = [
        item for item in items
        if item.get("type") not in {"data_quality", "quiet_market"}
    ]

    if not meaningful:
        return "Сильных ценовых или объёмных сигналов по текущим порогам нет."

    parts = []

    for item in meaningful[:5]:
        parts.append(item.get("description") or item.get("title") or "")

    return " ".join(part for part in parts if part)




def build_portfolio_context(portfolio: dict[str, Any]) -> str:
    if not portfolio.get("ok"):
        return "Портфель не рассчитан."

    total_value = portfolio.get("total_value")
    daily_pnl_abs = portfolio.get("daily_pnl_abs")
    daily_pnl_pct = portfolio.get("daily_pnl_pct")
    concentration = portfolio.get("concentration", {})
    max_position = concentration.get("max_position") or {}
    max_sector = concentration.get("max_sector") or {}

    lines = [
        f"Стоимость портфеля: {total_value} руб.",
        f"Дневное изменение: {daily_pnl_abs} руб. / {daily_pnl_pct}%.",
        f"Концентрация: {concentration.get('label')}.",
    ]

    if max_position:
        lines.append(
            f"Крупнейшая позиция: {max_position.get('ticker')} — {max_position.get('weight_pct')}% портфеля."
        )

    if max_sector:
        lines.append(
            f"Крупнейший сектор: {max_sector.get('sector')} — {max_sector.get('weight_pct')}%."
        )

    related = portfolio.get("related_events") or []
    related_tickers = [item.get("ticker") for item in related if item.get("ticker")]

    if related_tickers:
        lines.append("Связанные события есть по бумагам: " + ", ".join(related_tickers) + ".")

    return "\n".join(f"- {line}" for line in lines)

def build_risk_review(
    market: dict[str, Any],
    portfolio: dict[str, Any],
) -> str:
    notes: list[str] = []

    notes.extend(market.get("risk_notes", []))

    if portfolio.get("ok"):
        notes.extend(portfolio.get("risk_notes", []))

    if not notes:
        return "Критичных рисков по текущим данным не найдено."

    unique_notes = []
    seen = set()

    for note in notes:
        if note in seen:
            continue
        seen.add(note)
        unique_notes.append(note)

    return " ".join(unique_notes[:5])





def build_watchlist_context(
    market: dict[str, Any],
    portfolio: dict[str, Any],
) -> str:
    lines = []

    market_items = []
    seen_market = set()

    for item in market.get("watchlist", []):
        ticker = item.get("ticker")
        reason = item.get("reason")

        if not ticker or ticker in seen_market:
            continue

        seen_market.add(ticker)
        market_items.append(f"- {ticker}: {reason}")

    if market_items:
        lines.append("Рыночный фокус:")
        lines.extend(market_items[:4])

    if portfolio.get("ok"):
        positions = portfolio.get("positions", [])

        if positions:
            lines.append("")
            lines.append("Позиции портфеля:")

            for item in positions[:6]:
                ticker = item.get("ticker")
                weight = item.get("weight_pct")
                daily = item.get("daily_pnl_pct")

                if ticker:
                    lines.append(f"- {ticker}: доля {weight}%, день {daily}%")

    if not lines:
        return "Watchlist пустой."

    return "\n".join(lines)

def build_conclusion(
    market: dict[str, Any],
    events: dict[str, Any],
    portfolio: dict[str, Any],
) -> str:
    mood = market.get("market_mood")
    important_events_count = events.get("events_count", 0)

    parts = [
        f"Итог: рынок сейчас выглядит как {mood}.",
    ]

    if important_events_count:
        parts.append(
            f"Событийный фон активный: найдено важных событий {important_events_count}."
        )

    if portfolio.get("ok"):
        concentration = portfolio.get("concentration", {}).get("label")
        parts.append(
            f"По портфелю ключевой акцент — {concentration}."
        )

    parts.append(
        "Главная задача на следующий шаг — сопоставлять новые события с реакцией цены и оборотов."
    )

    return " ".join(parts)


def build_full_report(sections: dict[str, str]) -> str:
    labels = {
        "market_context": "1. Рыночный фон",
        "important_events": "2. Главные события",
        "market_signals": "3. Рыночные сигналы",
        "portfolio_context": "4. Портфель",
        "risk_review": "5. Риски",
        "watchlist": "6. Watchlist",
        "conclusion": "7. Вывод дня",
    }

    parts = []

    for key, title in labels.items():
        text = sections.get(key, "")
        parts.append(f"{title}\n{text}")

    return "\n\n".join(parts)
