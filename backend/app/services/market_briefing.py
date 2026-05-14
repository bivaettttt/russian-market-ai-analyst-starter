from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from app.services.market_radar import build_market_radar


SECTOR_MAP = {
    "SBER": "банки",
    "VTBR": "банки",
    "MOEX": "финансовая инфраструктура",

    "GAZP": "нефтегаз",
    "LKOH": "нефтегаз",
    "ROSN": "нефтегаз",
    "NVTK": "нефтегаз",
    "TATN": "нефтегаз",

    "GMKN": "металлы и добыча",
    "CHMF": "металлы и добыча",
    "MAGN": "металлы и добыча",
    "NLMK": "металлы и добыча",
    "ALRS": "металлы и добыча",
    "PLZL": "золото",

    "AFLT": "транспорт",
    "YNDX": "технологии",
}


def build_market_briefing(db: Session, limit: int = 5) -> dict[str, Any]:
    radar = build_market_radar(db=db, limit=limit)

    breadth = radar.get("breadth", {})
    up = breadth.get("up", 0)
    down = breadth.get("down", 0)
    flat = breadth.get("flat", 0)

    top_gainers = radar.get("top_gainers", [])
    top_losers = radar.get("top_losers", [])
    weakest_movers = radar.get("weakest_movers", [])
    most_traded = radar.get("most_traded_by_value", [])
    stale_tickers = radar.get("stale_tickers", [])

    market_mood = infer_market_mood(up=up, down=down, flat=flat)
    sector_heat = build_sector_heat(top_gainers=top_gainers, weakest_movers=weakest_movers)
    key_observations = build_key_observations(
        market_mood=market_mood,
        top_gainers=top_gainers,
        top_losers=top_losers,
        weakest_movers=weakest_movers,
        most_traded=most_traded,
        sector_heat=sector_heat,
        stale_tickers=stale_tickers,
    )

    return {
        "market": radar.get("market"),
        "date": radar.get("latest_date"),
        "market_mood": market_mood,
        "breadth": breadth,
        "key_observations": key_observations,
        "sector_heat": sector_heat,
        "top_gainers": top_gainers,
        "top_losers": top_losers,
        "weakest_movers": weakest_movers,
        "most_traded_by_value": most_traded,
        "data_quality": {
            "tickers_analyzed": radar.get("tickers_analyzed"),
            "stale_tickers_count": len(stale_tickers),
            "stale_tickers": stale_tickers,
        },
        "briefing": build_text_briefing(
            date=radar.get("latest_date"),
            market_mood=market_mood,
            key_observations=key_observations,
            stale_tickers=stale_tickers,
        ),
    }


def infer_market_mood(up: int, down: int, flat: int) -> str:
    total = up + down + flat

    if total == 0:
        return "нет данных"

    up_share = up / total
    down_share = down / total

    if up_share >= 0.75:
        return "широкий рост"
    if down_share >= 0.75:
        return "широкое снижение"
    if up > down:
        return "умеренно позитивный рынок"
    if down > up:
        return "умеренно негативный рынок"

    return "смешанная динамика"


def build_sector_heat(
    top_gainers: list[dict[str, Any]],
    weakest_movers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sector_scores: dict[str, list[float]] = defaultdict(list)

    for item in top_gainers:
        sector = SECTOR_MAP.get(item["ticker"], "прочее")
        sector_scores[sector].append(float(item.get("change_pct") or 0))

    for item in weakest_movers:
        sector = SECTOR_MAP.get(item["ticker"], "прочее")
        sector_scores[sector].append(float(item.get("change_pct") or 0))

    result = []
    for sector, values in sector_scores.items():
        avg_change = sum(values) / len(values)
        result.append(
            {
                "sector": sector,
                "avg_change_pct": round(avg_change, 2),
                "sample_size": len(values),
            }
        )

    return sorted(result, key=lambda item: item["avg_change_pct"], reverse=True)


def build_key_observations(
    market_mood: str,
    top_gainers: list[dict[str, Any]],
    top_losers: list[dict[str, Any]],
    weakest_movers: list[dict[str, Any]],
    most_traded: list[dict[str, Any]],
    sector_heat: list[dict[str, Any]],
    stale_tickers: list[dict[str, Any]],
) -> list[str]:
    observations: list[str] = []

    observations.append(f"Общее состояние рынка: {market_mood}.")

    if top_gainers:
        leader = top_gainers[0]
        observations.append(
            f"Главный лидер роста: {leader['ticker']} с изменением {leader['change_pct']}%."
        )

    if top_losers:
        laggard = top_losers[0]
        observations.append(
            f"Главный лидер снижения: {laggard['ticker']} с изменением {laggard['change_pct']}%."
        )
    elif weakest_movers:
        weakest = weakest_movers[0]
        observations.append(
            f"Падающих бумаг среди анализируемых тикеров нет; слабейшая динамика у {weakest['ticker']}."
        )

    if most_traded:
        traded = most_traded[0]
        value_bln = round((traded.get("value") or 0) / 1_000_000_000, 2)
        observations.append(
            f"Наибольший оборот у {traded['ticker']}: около {value_bln} млрд руб."
        )

    if sector_heat:
        strongest_sector = sector_heat[0]
        observations.append(
            f"Сильнее всего выглядит сектор: {strongest_sector['sector']}."
        )

    if stale_tickers:
        tickers = ", ".join(item["ticker"] for item in stale_tickers)
        observations.append(
            f"Из анализа исключены бумаги со старыми данными: {tickers}."
        )

    return observations


def build_text_briefing(
    date: str | None,
    market_mood: str,
    key_observations: list[str],
    stale_tickers: list[dict[str, Any]],
) -> str:
    header = f"Рыночный briefing на {date}: {market_mood}." if date else f"Рыночный briefing: {market_mood}."
    body = " ".join(key_observations)

    if stale_tickers:
        body += " Данные по части бумаг устарели, поэтому их нельзя смешивать с текущей торговой сессией."

    return f"{header} {body}"
