from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_, select, func
from sqlalchemy.orm import Session

from app.models import MarketEvent
from app.services.ticker_data import get_ticker_snapshot
from app.models import Candle, Instrument
from app.services.consumer_probability import build_probability_assessment
from app.services.ml_probability_engine import predict_ml_probability_for_ticker

CONSUMER_SIGNAL_MODEL_VERSION = "tech_v4_quality_rr"

ACTION_RANK = {
    "buy": 1,
    "consider_buy": 2,
    "watch_ml_confirmed": 3,
    "watch_ml_rejected": 4,
    "watch": 5,
    "watch_bad_rr": 6,
    "avoid_downside_signal": 7,
    "avoid_bad_target": 8,
    "avoid_bad_rr": 9,
    "avoid_ml_veto": 10,
    "avoid_ml_filter": 9,
    "avoid_risk": 10,
    "avoid": 11,
    "no_forecast": 9,
    "no_data": 9,
    "no_price": 9,

    # legacy actions
    "buy_watch": 2,
    "watch_buy": 2,
    "hold_watch": 4,
    "risk_sell_watch": 6,
}


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: Any, digits: int = 2) -> float | None:
    number = _to_float(value)
    if number is None:
        return None
    return round(number, digits)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return (current - previous) / previous * 100


def _event_to_dict(event: MarketEvent, relation_scope: str = "related") -> dict[str, Any]:
    created_at = getattr(event, "created_at", None)
    if isinstance(created_at, datetime):
        created_value = created_at.isoformat()
    else:
        created_value = str(created_at) if created_at else None

    raw_analysis = getattr(event, "raw_analysis", None)
    analysis: dict[str, Any] = {}

    if raw_analysis:
        try:
            parsed = json.loads(raw_analysis)
            if isinstance(parsed, dict):
                analysis = parsed
        except Exception:
            analysis = {}

    affected_assets = getattr(event, "affected_assets", None) or analysis.get("affected_assets")
    affected_sectors = analysis.get("affected_sectors") or analysis.get("sectors") or []

    return {
        "id": getattr(event, "id", None),
        "title": getattr(event, "title", None) or analysis.get("title") or "Событие рынка",
        "text": getattr(event, "text", None),
        "source": getattr(event, "source", None),
        "url": getattr(event, "url", None),
        "importance": getattr(event, "importance", None) or analysis.get("importance"),
        "impact": getattr(event, "impact", None) or analysis.get("impact"),
        "event_type": analysis.get("event_type") or "other",
        "affected_assets": affected_assets,
        "affected_sectors": affected_sectors,
        "time_horizon": analysis.get("time_horizon"),
        "confidence": analysis.get("confidence"),
        "watch_next": analysis.get("watch_next") or [],
        "created_at": created_value,
        "reasoning": getattr(event, "reasoning", None) or analysis.get("reasoning"),
        "relation_scope": relation_scope,
    }


def list_related_events(
    db: Session,
    ticker: str,
    limit: int = 3,
) -> list[dict[str, Any]]:
    ticker = ticker.upper().strip()

    rows = db.scalars(
        select(MarketEvent)
        .where(
            or_(
                MarketEvent.affected_assets.ilike(f"%{ticker}%"),
                MarketEvent.title.ilike(f"%{ticker}%"),
                MarketEvent.text.ilike(f"%{ticker}%"),
            )
        )
        .order_by(MarketEvent.created_at.desc())
        .limit(limit)
    ).all()

    return [_event_to_dict(row) for row in rows]



def list_global_market_events(
    db: Session,
    limit: int = 12,
) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(MarketEvent)
        .order_by(MarketEvent.created_at.desc())
        .limit(limit)
    ).all()

    return [_event_to_dict(row, relation_scope="global") for row in rows]


def _merge_events(
    related_events: list[dict[str, Any]],
    global_events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()

    for event in [*(related_events or []), *(global_events or [])]:
        key = str(event.get("id") or event.get("url") or event.get("title") or "")
        if key and key in seen:
            continue

        if key:
            seen.add(key)

        result.append(event)

    return result

def _build_unified_signal(
    candles: list[dict[str, Any]],
    latest: dict[str, Any],
    technical: dict[str, Any],
    fallback_signal: dict[str, Any],
) -> dict[str, Any]:
    try:
        from app.services.signals_backtest import build_historical_signal_v4

        candle = candles[-1] if candles else latest
        signal = build_historical_signal_v4(
            history=candles or [latest],
            candle=candle,
            technical=technical,
        )
        signal["model_version"] = CONSUMER_SIGNAL_MODEL_VERSION
        return signal
    except Exception as exc:
        signal = dict(fallback_signal or {})
        signal["model_version"] = "fallback_consumer_signal"
        signal["fallback_error"] = str(exc)
        return signal


def _recommendation_from_action(action: str | None, probability: float | None) -> tuple[str, str]:
    probability = probability or 0

    if action in {"buy_watch", "watch_buy"}:
        if probability >= 70:
            return "Покупать", "positive"
        return "Можно рассмотреть", "positive"

    if action == "risk_sell_watch":
        return "Высокий риск", "negative"

    return "Наблюдать", "neutral"


def _derive_target_price(
    price: float | None,
    signal: dict[str, Any],
    technical: dict[str, Any],
) -> float | None:
    explicit_target = _to_float(signal.get("target_price"))

    if price is None:
        return round(explicit_target, 2) if explicit_target is not None else None

    action = signal.get("action")
    recent_high = _to_float(technical.get("recent_high"))
    recent_low = _to_float(technical.get("recent_low"))
    sma_20 = _to_float(technical.get("sma_20"))
    sma_50 = _to_float(technical.get("sma_50"))
    volatility = _to_float(technical.get("volatility_20d_pct")) or 1.5

    normalized_volatility = min(max(volatility, 1.0), 4.0)

    if action == "risk_sell_watch":
        if explicit_target is not None and explicit_target < price:
            return round(explicit_target, 2)

        candidate = min(
            price * (1 - normalized_volatility / 100 * 2),
            recent_low or price,
        )
        return round(candidate, 2)

    # Consumer long targets must not be almost equal to current price.
    # If an upstream model gives a tiny target like +0.2%, normalize it
    # using volatility and nearby technical levels.
    min_upside_pct = max(2.8, min(5.5, normalized_volatility * 1.8))
    minimum_consumer_target = price * (1 + min_upside_pct / 100)

    candidates = [minimum_consumer_target]

    if explicit_target is not None and explicit_target > price * 1.02:
        candidates.append(explicit_target)

    if recent_high is not None and recent_high > price * 1.01:
        candidates.append(recent_high)

    if sma_20 is not None and sma_20 > price * 1.01:
        candidates.append(sma_20)

    if sma_50 is not None and sma_50 > price * 1.01:
        candidates.append(sma_50)

    if action in {"buy_watch", "watch_buy"}:
        candidates.append(price * 1.035)

    candidate = max(candidates)

    # Do not create unrealistic consumer targets from a single noisy level.
    max_reasonable_target = price * (1 + max(8.0, normalized_volatility * 3.2) / 100)

    return round(min(candidate, max_reasonable_target), 2)


def _derive_forecast_range(
    price: float | None,
    target: float | None,
    signal: dict[str, Any],
    technical: dict[str, Any],
) -> dict[str, float | None]:
    if price is None:
        return {"low": None, "high": None}

    action = signal.get("action")
    recent_high = _to_float(technical.get("recent_high"))
    recent_low = _to_float(technical.get("recent_low"))
    volatility = _to_float(technical.get("volatility_20d_pct")) or 1.5
    vol_buffer = min(max(volatility, 0.8), 4.5) / 100

    if action == "risk_sell_watch":
        low = min(recent_low or price * (1 - vol_buffer * 3), target or price)
        high = price * (1 + vol_buffer * 1.2)
        return {"low": round(low, 2), "high": round(high, 2)}

    if action in {"buy_watch", "watch_buy"}:
        low = max(0, price * (1 - vol_buffer * 1.6))
        high = max(target or price, recent_high or price, price * (1 + vol_buffer * 2.2))
        return {"low": round(low, 2), "high": round(high, 2)}

    low = min(recent_low or price * (1 - vol_buffer * 1.6), price * (1 - vol_buffer * 1.2))
    high = max(target or price, recent_high or price, price * (1 + vol_buffer * 1.6))
    return {"low": round(low, 2), "high": round(high, 2)}


def _calculate_target_probability(
    signal: dict[str, Any],
    technical: dict[str, Any],
    price: float | None,
    target_price: float | None,
    events: list[dict[str, Any]],
) -> float | None:
    if price is None or target_price is None:
        return None

    action = signal.get("action")
    confidence = _to_float(signal.get("confidence_pct"))
    quality = _to_float(signal.get("quality_score"))
    rr = _to_float(signal.get("risk_reward_ratio"))
    return_5d = _to_float(technical.get("return_5d_pct"))
    return_20d = _to_float(technical.get("return_20d_pct"))
    volume_ratio = _to_float(technical.get("volume_ratio"))
    volatility = _to_float(technical.get("volatility_20d_pct"))

    probability = confidence if confidence is not None else 50.0

    if quality is not None:
        probability += (quality - 50.0) * 0.28

    if rr is not None:
        if rr >= 1.8:
            probability += 8
        elif rr >= 1.2:
            probability += 4
        elif rr < 0.8:
            probability -= 10
        else:
            probability -= 4

    upside_pct = _pct_change(target_price, price)
    if upside_pct is not None:
        if action == "risk_sell_watch":
            # Для risk-сигнала цель часто ниже текущей цены. Тогда вероятность достижения цели снижения растёт.
            downside_pct = abs(upside_pct)
            if downside_pct <= 2:
                probability += 6
            elif downside_pct >= 8:
                probability -= 8
        else:
            if upside_pct <= 2:
                probability += 5
            elif upside_pct <= 5:
                probability += 1
            elif upside_pct >= 12:
                probability -= 10
            elif upside_pct >= 8:
                probability -= 5

    if return_5d is not None:
        if return_5d > 1:
            probability += 3 if action != "risk_sell_watch" else -2
        elif return_5d < -1:
            probability -= 3 if action != "risk_sell_watch" else -1

    if return_20d is not None:
        if return_20d > 3:
            probability += 2 if action != "risk_sell_watch" else -2
        elif return_20d < -4:
            probability -= 4 if action != "risk_sell_watch" else 2

    if volume_ratio is not None:
        if volume_ratio >= 1.3:
            probability += 3
        elif volume_ratio < 0.6:
            probability -= 4

    if volatility is not None:
        if volatility >= 3.0:
            probability -= 8
        elif volatility <= 1.2:
            probability += 2

    for event in events:
        impact = str(event.get("impact") or "").lower()
        importance = _to_float(event.get("importance")) or 0
        weight = min(max(importance, 1), 5)

        if "positive" in impact or "позит" in impact:
            probability += weight
        elif "negative" in impact or "негат" in impact:
            probability -= weight

    if action == "risk_sell_watch":
        probability = _clamp(probability, 12, 88)
    else:
        probability = _clamp(probability, 8, 92)

    return round(probability, 0)



def _parse_event_datetime(value: Any) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    text_value = str(value).strip()

    if not text_value:
        return None

    try:
        parsed = datetime.fromisoformat(text_value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def _event_direction_score(event: dict[str, Any]) -> int:
    impact = str(event.get("impact") or "").lower()
    event_type = str(event.get("event_type") or "").lower()
    title = str(event.get("title") or "").lower()
    reasoning = str(event.get("reasoning") or "").lower()
    blob = " ".join([impact, event_type, title, reasoning])

    positive_words = {
        "positive", "bullish", "growth", "upgrade", "beat", "buyback",
        "позит", "рост", "выше ожид", "дивиденд", "байбек", "прибыль",
        "увелич", "одобр", "контракт", "сильн", "улучш",
    }

    negative_words = {
        "negative", "bearish", "decline", "downgrade", "miss", "sanction",
        "risk", "lawsuit", "default", "loss",
        "негат", "паден", "сниж", "санкц", "риск", "штраф", "убыт",
        "запрет", "огранич", "хуже ожид", "слаб",
    }

    positive_hits = sum(1 for word in positive_words if word in blob)
    negative_hits = sum(1 for word in negative_words if word in blob)

    if positive_hits > negative_hits:
        return 1

    if negative_hits > positive_hits:
        return -1

    if "positive" in impact:
        return 1

    if "negative" in impact:
        return -1

    return 0



def _as_text_list(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    if isinstance(value, tuple | set):
        return [str(item).strip() for item in value if str(item).strip()]

    raw = str(value).replace(";", ",").replace("|", ",")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _event_blob(event: dict[str, Any]) -> str:
    parts = [
        event.get("title"),
        event.get("event_type"),
        event.get("impact"),
        event.get("source"),
        event.get("reasoning"),
        event.get("affected_assets"),
        event.get("sectors"),
    ]

    return " ".join(str(part or "") for part in parts).lower()


def _source_reliability_score(event: dict[str, Any]) -> int:
    source = str(event.get("source") or "").lower()
    url = str(event.get("url") or "").lower()
    blob = f"{source} {url}"

    official_sources = [
        "cbr.ru",
        "moex.com",
        "e-disclosure",
        "e-disclosure.ru",
        "disclosure",
        "минфин",
        "minfin",
        "government",
        "правительство",
    ]

    strong_media = [
        "interfax",
        "tass",
        "rbc",
        "vedomosti",
        "kommersant",
        "forbes",
    ]

    if any(marker in blob for marker in official_sources):
        return 95

    if any(marker in blob for marker in strong_media):
        return 82

    if "company" in blob or "issuer" in blob or "эмитент" in blob:
        return 88

    if source:
        return 65

    return 45


def _event_scope(
    event: dict[str, Any],
    *,
    ticker: str | None,
    instrument: dict[str, Any] | None,
) -> str:
    ticker_text = str(ticker or "").upper().strip()
    name_text = str((instrument or {}).get("name") or "").lower().strip()
    blob = _event_blob(event)
    event_type = str(event.get("event_type") or "").lower()

    affected_assets = [item.upper() for item in _as_text_list(event.get("affected_assets"))]
    sectors = _as_text_list(event.get("sectors"))

    if ticker_text and ticker_text in affected_assets:
        return "company"

    if ticker_text and ticker_text.lower() in blob:
        return "company"

    if name_text and len(name_text) >= 4 and name_text in blob:
        return "company"

    if sectors or event_type in {"banking", "consumer_finance", "commodities", "oil", "gas", "metals"}:
        return "sector"

    if event_type in {"rates", "bonds", "fx", "macro", "regulation", "sanctions"}:
        return "macro"

    return "market"


def _ticker_relevance_score(
    event: dict[str, Any],
    *,
    ticker: str | None,
    instrument: dict[str, Any] | None,
) -> int:
    ticker_text = str(ticker or "").upper().strip()
    name_text = str((instrument or {}).get("name") or "").lower().strip()
    blob = _event_blob(event)
    event_type = str(event.get("event_type") or "").lower()

    affected_assets = [item.upper() for item in _as_text_list(event.get("affected_assets"))]
    sectors = [item.lower() for item in _as_text_list(event.get("sectors"))]

    if ticker_text and ticker_text in affected_assets:
        return 98

    if ticker_text and ticker_text.lower() in blob:
        return 90

    if name_text and len(name_text) >= 4 and name_text in blob:
        return 86

    if affected_assets and any(item in {"IMOEX", "MOEX", "RUB", "USD", "CNY", "ALL", "MARKET"} for item in affected_assets):
        return 48

    if event_type in {"rates", "fx", "bonds", "macro"}:
        return 45

    if event_type in {"regulation", "sanctions"}:
        return 55

    if event_type in {"banking", "consumer_finance"}:
        instrument_name = name_text
        if any(marker in instrument_name for marker in ["банк", "bank", "сбер", "втб", "тинькофф"]):
            return 72
        return 46

    if sectors:
        return 58

    return 35


def _apply_news_relevance_scoring(
    *,
    news_assessment: dict[str, Any],
    events: list[dict[str, Any]],
    ticker: str | None,
    instrument: dict[str, Any] | None,
) -> dict[str, Any]:
    if not news_assessment.get("has_events") or not events:
        news_assessment.update(
            {
                "ticker_relevance_score": 0,
                "source_reliability_score": 0,
                "event_scope": "none",
                "news_effect": "none",
                "relevance_events": [],
            }
        )
        return news_assessment

    enriched_events: list[dict[str, Any]] = []
    relevance_weighted = 0.0
    reliability_weighted = 0.0
    total_weight = 0.0
    scopes: dict[str, int] = {}

    for event in events[:8]:
        importance = _to_float(event.get("importance")) or 5.0
        importance = min(max(importance, 1.0), 10.0)

        relevance = _ticker_relevance_score(
            event,
            ticker=ticker,
            instrument=instrument,
        )
        reliability = _source_reliability_score(event)
        scope = _event_scope(
            event,
            ticker=ticker,
            instrument=instrument,
        )

        total_weight += importance
        relevance_weighted += relevance * importance
        reliability_weighted += reliability * importance
        scopes[scope] = scopes.get(scope, 0) + 1

        enriched_events.append(
            {
                "title": event.get("title"),
                "source": event.get("source"),
                "impact": event.get("impact"),
                "importance": event.get("importance"),
                "scope": scope,
                "ticker_relevance_score": relevance,
                "source_reliability_score": reliability,
            }
        )

    ticker_relevance = int(round(relevance_weighted / total_weight, 0)) if total_weight else 0
    source_reliability = int(round(reliability_weighted / total_weight, 0)) if total_weight else 0
    event_scope = max(scopes.items(), key=lambda item: item[1])[0] if scopes else "market"

    original_adjustment = _to_float(news_assessment.get("adjustment_pct")) or 0.0

    relevance_factor = _clamp(ticker_relevance / 100.0, 0.15, 1.0)
    reliability_factor = _clamp(source_reliability / 100.0, 0.45, 1.0)

    adjusted = round(original_adjustment * relevance_factor * reliability_factor, 1)

    sentiment = str(news_assessment.get("sentiment") or "none")
    impact_score = _to_float(news_assessment.get("impact_score")) or 0
    confidence = _to_float(news_assessment.get("confidence")) or 0

    if ticker_relevance < 35:
        adjusted = round(_clamp(adjusted, -0.8, 0.8), 1)
        news_effect = "info_only"
    elif sentiment == "negative" and impact_score >= 80 and confidence >= 70 and ticker_relevance >= 65:
        news_effect = "veto"
    elif adjusted >= 0.8:
        news_effect = "boost"
    elif adjusted <= -0.8:
        news_effect = "penalty"
    else:
        news_effect = "info_only"

    news_assessment["adjustment_pct"] = adjusted
    news_assessment["ticker_relevance_score"] = ticker_relevance
    news_assessment["source_reliability_score"] = source_reliability
    news_assessment["event_scope"] = event_scope
    news_assessment["news_effect"] = news_effect
    news_assessment["relevance_events"] = enriched_events[:5]

    base_summary = str(news_assessment.get("summary") or "").strip()
    relevance_summary = (
        f" Релевантность к тикеру: {ticker_relevance}/100; "
        f"надёжность источников: {source_reliability}/100; "
        f"scope={event_scope}; effect={news_effect}."
    )

    news_assessment["summary"] = (base_summary + relevance_summary).strip()

    risk_flags = list(news_assessment.get("risk_flags") or [])

    if news_effect == "veto":
        risk_flags.append("новостной veto: сильный релевантный негатив")
    elif news_effect == "penalty":
        risk_flags.append("релевантный негативный новостной фон")
    elif news_effect == "info_only":
        risk_flags.append("новость учитывается информационно, влияние ограничено")

    news_assessment["risk_flags"] = risk_flags

    return news_assessment



def _instrument_impact_groups(
    *,
    ticker: str | None,
    instrument: dict[str, Any] | None,
) -> set[str]:
    ticker_text = str(ticker or "").upper().strip()
    name = str((instrument or {}).get("name") or "").lower()
    sector = str((instrument or {}).get("sector") or "").lower()
    asset_type = str((instrument or {}).get("asset_type") or "").lower()

    groups: set[str] = {"market"}

    if asset_type in {"stock", "share", "equity", "unknown"}:
        groups.add("equity")

    if asset_type in {"bond", "ofz"} or "офз" in name or ticker_text.startswith("SU"):
        groups.add("ofz")
        groups.add("bonds")

    banks = {"SBER", "SBERP", "VTBR", "T", "TCSG", "BSPB", "BSPBP", "CBOM", "MOEX", "SPBE"}
    oil_gas = {"LKOH", "ROSN", "TATN", "TATNP", "SNGS", "SNGSP", "GAZP", "NVTK", "TRNFP"}
    airlines = {"AFLT"}
    gold = {"PLZL", "POLY", "SELG"}
    developers = {"PIKK", "SMLT", "LSRG", "ETLN"}
    metals = {"GMKN", "RUAL", "CHMF", "NLMK", "MAGN", "MTLR", "MTLRP"}
    fertilizers = {"PHOR", "AKRN"}
    retailers = {"MGNT", "FIVE", "LENT", "OZON", "WUSH"}
    importers = airlines | retailers | developers | {"OZON", "FIVE", "MGNT"}
    exporters = oil_gas | metals | fertilizers | {"ALRS"}

    if ticker_text in banks or "банк" in name or "bank" in name or "финанс" in sector:
        groups.add("banks")

    if ticker_text in {"MOEX", "SPBE"}:
        groups.add("exchanges")

    if ticker_text in oil_gas or "нефт" in name or "газ" in name or "нефт" in sector or "газ" in sector:
        groups.add("oil_gas")
        groups.add("exporters")

    if ticker_text in airlines or "аэрофлот" in name or "авиа" in name:
        groups.add("airlines")
        groups.add("importers")

    if ticker_text in gold or "золот" in name:
        groups.add("gold")

    if ticker_text in developers or "девел" in name or "строит" in name:
        groups.add("developers")
        groups.add("rate_sensitive")

    if ticker_text in metals:
        groups.add("metals")
        groups.add("exporters")

    if ticker_text in fertilizers:
        groups.add("fertilizers")
        groups.add("exporters")

    if ticker_text in retailers:
        groups.add("retail")
        groups.add("consumer")

    if ticker_text in exporters:
        groups.add("exporters")

    if ticker_text in importers:
        groups.add("importers")

    return groups


def _global_event_tags(event: dict[str, Any]) -> set[str]:
    blob = _event_blob(event)
    event_type = str(event.get("event_type") or "").lower()
    tags: set[str] = set()

    if event_type in {"rates", "bonds"} or "ключев" in blob or "ставк" in blob or "офз" in blob:
        if any(word in blob for word in ["сниз", "пониз", "смягч", "ниже"]):
            tags.add("rates_down")
            tags.add("bonds_positive")
            tags.add("rate_sensitive_positive")
        elif any(word in blob for word in ["повыс", "ужесточ", "выше"]):
            tags.add("rates_up")
            tags.add("bonds_negative")
            tags.add("rate_sensitive_negative")
        else:
            tags.add("rates_mixed")

    if event_type in {"sanctions", "regulation"} or "санкц" in blob:
        if any(word in blob for word in ["сняти", "снял", "смягч", "отмен", "послаб", "исключил"]):
            tags.add("sanctions_easing")
            tags.add("russia_risk_premium_down")
        else:
            tags.add("sanctions_tightening")
            tags.add("russia_risk_premium_up")

    if (
        "иран" in blob
        or "сша" in blob and "иран" in blob
        or "ормуз" in blob
        or "персид" in blob
        or "ближн" in blob
        or "военн" in blob
        or "удар" in blob
        or "ракета" in blob
        or "эскалац" in blob
        or "конфликт" in blob
        or "геополит" in blob
    ):
        tags.add("geopolitical_risk")
        tags.add("risk_off")

        if "нефт" in blob or "brent" in blob or "баррел" in blob or "ормуз" in blob:
            tags.add("oil_shock")

    if event_type in {"fx"} or "рубл" in blob or "курс" in blob or "usd" in blob or "доллар" in blob:
        if any(word in blob for word in ["ослаб", "слаб", "дешев", "девальв"]):
            tags.add("ruble_weak")
            tags.add("exporters_positive")
            tags.add("importers_negative")
        elif any(word in blob for word in ["укреп", "сильн", "дороже"]):
            tags.add("ruble_strong")
            tags.add("exporters_negative")
            tags.add("importers_positive")
        else:
            tags.add("fx_mixed")

    if event_type in {"commodities"} or "нефт" in blob or "газ" in blob or "металл" in blob or "золото" in blob:
        tags.add("commodities")

        if "нефт" in blob or "brent" in blob:
            tags.add("oil_market")

        if "золото" in blob:
            tags.add("gold_market")

    if event_type in {"macro"}:
        tags.add("macro")

    return tags


def _impact_from_global_tags(
    *,
    tags: set[str],
    groups: set[str],
) -> tuple[float, list[str], list[str]]:
    score = 0.0
    reasons: list[str] = []
    affected_groups: list[str] = []

    def add(value: float, reason: str, group: str) -> None:
        nonlocal score
        score += value
        reasons.append(reason)
        affected_groups.append(group)

    if "rates_down" in tags:
        if "ofz" in groups or "bonds" in groups:
            add(1.45, "снижение ставки заметно поддерживает ОФЗ/облигации", "bonds")
        if "developers" in groups or "rate_sensitive" in groups:
            add(0.95, "снижение ставки поддерживает чувствительные к кредиту сектора", "rate_sensitive")
        if "banks" in groups:
            add(0.45, "снижение ставки умеренно поддерживает кредитный спрос банков", "banks")
        if "equity" in groups:
            add(0.30, "снижение ставки снижает дисконтирование акций", "equity")

    if "rates_up" in tags:
        if "ofz" in groups or "bonds" in groups:
            add(-1.35, "рост ставки давит на облигации", "bonds")
        if "developers" in groups or "rate_sensitive" in groups:
            add(-0.95, "рост ставки ухудшает условия для кредитозависимых секторов", "rate_sensitive")
        if "equity" in groups:
            add(-0.30, "рост ставки повышает дисконтирование акций", "equity")

    if "oil_shock" in tags or "oil_market" in tags:
        if "oil_gas" in groups:
            add(1.15, "геополитический/сырьевой риск поддерживает нефтегаз", "oil_gas")
        if "airlines" in groups:
            add(-1.05, "рост нефтяных рисков ухудшает картину для авиаперевозчиков", "airlines")
        if "gold" in groups:
            add(0.55, "геополитический risk-off поддерживает золото и защитные активы", "gold")
        if "equity" in groups or "market" in groups:
            add(-0.25, "геополитический risk-off давит на широкий рынок", "market")

    if "geopolitical_risk" in tags and "oil_shock" not in tags:
        if "gold" in groups:
            add(0.55, "геополитический риск поддерживает защитные активы", "gold")
        if "equity" in groups:
            add(-0.35, "risk-off ухудшает фон для широкого рынка", "market")
        if "airlines" in groups:
            add(-0.65, "геополитический риск ухудшает фон для авиаперевозчиков", "airlines")

    if "sanctions_easing" in tags:
        if "banks" in groups:
            add(1.0, "смягчение санкций поддерживает банки", "banks")
        if "exchanges" in groups:
            add(0.9, "смягчение санкций поддерживает биржевую инфраструктуру", "exchanges")
        if "equity" in groups:
            add(0.55, "смягчение санкций поддерживает широкий рынок РФ", "market")
        if "exporters" in groups:
            add(0.25, "смягчение санкций снижает операционную премию риска экспортёров", "exporters")

    if "sanctions_tightening" in tags:
        if "banks" in groups:
            add(-1.0, "санкционное давление негативно для банков", "banks")
        if "exchanges" in groups:
            add(-0.9, "санкционные риски негативны для биржевой инфраструктуры", "exchanges")
        if "equity" in groups:
            add(-0.5, "санкционное давление ухудшает фон широкого рынка", "market")
        if "exporters" in groups:
            add(-0.25, "санкции могут ухудшать операционные условия экспортёров", "exporters")

    if "ruble_weak" in tags:
        if "exporters" in groups:
            add(0.65, "слабый рубль поддерживает экспортёров", "exporters")
        if "importers" in groups or "airlines" in groups:
            add(-0.65, "слабый рубль давит на импортозависимые компании", "importers")
        if "retail" in groups or "consumer" in groups:
            add(-0.25, "слабый рубль может усиливать инфляционное давление", "consumer")

    if "ruble_strong" in tags:
        if "exporters" in groups:
            add(-0.45, "сильный рубль ухудшает рублёвую выручку экспортёров", "exporters")
        if "importers" in groups or "airlines" in groups:
            add(0.45, "сильный рубль поддерживает импортозависимые компании", "importers")
        if "retail" in groups or "consumer" in groups:
            add(0.20, "сильный рубль смягчает инфляционное давление для потребительского сектора", "consumer")

    return score, reasons[:6], sorted(set(affected_groups))


def _build_global_event_assessment(
    *,
    events: list[dict[str, Any]],
    ticker: str | None,
    instrument: dict[str, Any] | None,
    scenario_direction: str | None,
) -> dict[str, Any]:
    groups = _instrument_impact_groups(ticker=ticker, instrument=instrument)
    scenario = str(scenario_direction or "long").lower()

    if not events:
        return {
            "has_global_events": False,
            "adjustment_pct": 0.0,
            "tags": [],
            "affected_groups": sorted(groups),
            "macro_regime_flags": [],
            "reason": "Глобальных событий в базе нет.",
            "events": [],
        }

    total_score = 0.0
    used_events: list[dict[str, Any]] = []
    all_tags: set[str] = set()
    all_reasons: list[str] = []
    affected: set[str] = set()

    for event in events[:12]:
        tags = _global_event_tags(event)

        if not tags:
            continue

        score, reasons, affected_groups = _impact_from_global_tags(
            tags=tags,
            groups=groups,
        )

        if abs(score) < 0.05:
            continue

        importance = _to_float(event.get("importance")) or 5.0
        importance_factor = min(max(importance / 10.0, 0.25), 1.0)

        reliability = _source_reliability_score(event) / 100.0
        event_score = score * importance_factor * reliability

        total_score += event_score
        all_tags.update(tags)
        all_reasons.extend(reasons)
        affected.update(affected_groups)

        used_events.append(
            {
                "title": event.get("title"),
                "event_type": event.get("event_type"),
                "impact": event.get("impact"),
                "importance": event.get("importance"),
                "source": event.get("source"),
                "tags": sorted(tags),
                "score": _round(event_score, 3),
                "reasons": reasons,
            }
        )

    # score > 0 поддерживает long. Для downside-сценария знак разворачиваем:
    # негативный фон повышает вероятность downside, позитивный снижает.
    if scenario == "downside":
        total_score *= -1

    adjustment = _round(_clamp(total_score * 2.2, -5.0, 5.0), 1)

    if adjustment > 0:
        direction_text = "поддерживает текущий сценарий"
    elif adjustment < 0:
        direction_text = "ослабляет текущий сценарий"
    else:
        direction_text = "существенно не меняет сценарий"

    reason = (
        f"Глобальный событийный фон {direction_text}: "
        f"adjustment={adjustment:+.1f} п.п.; "
        f"tags={', '.join(sorted(all_tags)) or 'none'}."
    )

    if all_reasons:
        reason += " " + "; ".join(dict.fromkeys(all_reasons[:5])) + "."

    return {
        "has_global_events": bool(used_events),
        "adjustment_pct": adjustment,
        "tags": sorted(all_tags),
        "affected_groups": sorted(affected or groups),
        "macro_regime_flags": sorted(all_tags),
        "reason": reason,
        "events": used_events[:8],
    }


def _build_news_assessment(
    *,
    events: list[dict[str, Any]],
    scenario_direction: str | None,
) -> dict[str, Any]:
    scenario = str(scenario_direction or "neutral").lower()

    if not events:
        return {
            "has_events": False,
            "sentiment": "none",
            "sentiment_score": 0,
            "impact_score": 0,
            "confidence": 0,
            "freshness_score": 0,
            "source_count": 0,
            "positive_events": [],
            "negative_events": [],
            "risk_events": [],
            "adjustment_pct": 0.0,
            "risk_flags": [],
            "summary": "Свежих событий по тикеру в базе нет. Новостной слой не менял вероятность.",
        }

    now = datetime.now(timezone.utc)

    raw_score = 0.0
    total_weight = 0.0
    freshness_values: list[float] = []
    positive_events: list[dict[str, Any]] = []
    negative_events: list[dict[str, Any]] = []
    risk_events: list[dict[str, Any]] = []

    for event in events[:8]:
        direction = _event_direction_score(event)
        importance = _to_float(event.get("importance")) or 5.0
        importance = min(max(importance, 1.0), 10.0)

        created_at = _parse_event_datetime(event.get("created_at"))
        if created_at is not None:
            age_days = max((now - created_at).total_seconds() / 86400, 0)
            if age_days <= 2:
                freshness = 100.0
            elif age_days <= 7:
                freshness = 82.0
            elif age_days <= 21:
                freshness = 55.0
            elif age_days <= 60:
                freshness = 30.0
            else:
                freshness = 12.0
        else:
            freshness = 45.0

        freshness_values.append(freshness)

        weight = importance * freshness / 100.0
        total_weight += weight

        contribution = direction * weight * 10.0
        raw_score += contribution

        compact = {
            "title": event.get("title"),
            "impact": event.get("impact"),
            "importance": event.get("importance"),
            "source": event.get("source"),
            "url": event.get("url"),
            "freshness_score": _round(freshness, 0),
        }

        if direction > 0:
            positive_events.append(compact)
        elif direction < 0:
            negative_events.append(compact)

        impact_blob = str(event.get("impact") or "").lower()
        if direction < 0 or "risk" in impact_blob or "риск" in impact_blob:
            risk_events.append(compact)

    sentiment_score = int(round(_clamp(raw_score, -100, 100), 0))
    impact_score = int(round(_clamp(total_weight * 10.0, 0, 100), 0))
    freshness_score = int(round(sum(freshness_values) / len(freshness_values), 0)) if freshness_values else 0
    confidence = int(round(_clamp(35 + len(events[:8]) * 9 + impact_score * 0.25, 0, 95), 0))

    if sentiment_score >= 25:
        sentiment = "positive"
    elif sentiment_score <= -25:
        sentiment = "negative"
    elif sentiment_score != 0:
        sentiment = "mixed"
    else:
        sentiment = "neutral"

    # Для long-сценария позитивные события повышают вероятность,
    # негативные снижают. Для downside-сценария знак разворачивается:
    # негативная новость подтверждает риск снижения.
    scenario_score = sentiment_score

    if scenario == "downside":
        scenario_score = -sentiment_score

    adjustment = round(_clamp(scenario_score / 100.0 * min(7.0, max(2.0, impact_score / 12.0)), -7.0, 7.0), 1)

    risk_flags: list[str] = []

    if sentiment == "negative" and scenario != "downside":
        risk_flags.append("негативный новостной фон для long-сценария")

    if risk_events:
        risk_flags.append("есть события риска")

    if freshness_score < 35:
        risk_flags.append("события устарели или недостаточно свежие")

    if sentiment == "positive":
        summary = f"Новостной фон положительный: sentiment_score={sentiment_score}, влияние на вероятность {adjustment:+.1f} п.п."
    elif sentiment == "negative":
        summary = f"Новостной фон негативный: sentiment_score={sentiment_score}, влияние на вероятность {adjustment:+.1f} п.п."
    elif sentiment == "mixed":
        summary = f"Новостной фон смешанный: sentiment_score={sentiment_score}, влияние на вероятность {adjustment:+.1f} п.п."
    else:
        summary = "Новостной фон нейтральный. Существенной корректировки вероятности нет."

    return {
        "has_events": True,
        "sentiment": sentiment,
        "sentiment_score": sentiment_score,
        "impact_score": impact_score,
        "confidence": confidence,
        "freshness_score": freshness_score,
        "source_count": len(events),
        "positive_events": positive_events[:5],
        "negative_events": negative_events[:5],
        "risk_events": risk_events[:5],
        "adjustment_pct": adjustment,
        "risk_flags": risk_flags,
        "summary": summary,
    }


def _apply_news_adjustment(
    probability: float | None,
    news_assessment: dict[str, Any],
) -> float | None:
    if probability is None:
        return None

    adjustment = _to_float(news_assessment.get("adjustment_pct")) or 0.0
    return _round(_clamp(float(probability) + adjustment, 1, 99), 0)


def _build_explanation(
    signal: dict[str, Any],
    technical: dict[str, Any],
    events: list[dict[str, Any]],
    probability: float | None,
    probability_assessment: dict[str, Any] | None = None,
    ml_probability_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    technical_factors = []

    if technical.get("trend"):
        technical_factors.append(f"Тренд: {technical.get('trend')}.")
    if technical.get("return_5d_pct") is not None:
        technical_factors.append(f"Динамика за 5 свечей: {technical.get('return_5d_pct')}%.")
    if technical.get("return_20d_pct") is not None:
        technical_factors.append(f"Динамика за 20 свечей: {technical.get('return_20d_pct')}%.")
    if technical.get("volume_ratio") is not None:
        technical_factors.append(f"Объём к среднему: {technical.get('volume_ratio')}x.")

    for reason in signal.get("reasons") or []:
        if reason and len(technical_factors) < 7:
            technical_factors.append(str(reason))

    news_factors = []
    if events:
        for event in events[:3]:
            title = event.get("title") or "Событие рынка"
            impact = event.get("impact") or "влияние не определено"
            news_factors.append(f"{title} — {impact}.")
    else:
        news_factors.append("Свежих событий по тикеру в базе не найдено; прогноз основан главным образом на цене и объёмах.")

    risk_factors = []
    risk_level = signal.get("risk_level")
    if risk_level:
        risk_factors.append(f"Риск сценария: {risk_level}.")
    if signal.get("stop_loss") is not None:
        risk_factors.append(f"Сценарий лучше пересмотреть около {signal.get('stop_loss')}.")
    if signal.get("risk_reward_ratio") is not None:
        risk_factors.append(f"Соотношение потенциальной цели и риска: {signal.get('risk_reward_ratio')}.")

    assessment = probability_assessment or {}
    news_internal = (assessment.get("internal") or {}).get("news_assessment") or {}

    if news_internal.get("summary"):
        news_factors.insert(0, str(news_internal.get("summary")))

    reliability_level = assessment.get("reliability_level")
    reliability_reasons = assessment.get("reliability_reasons") or []
    calibration = assessment.get("calibration") or {}
    liquidity = assessment.get("liquidity") or {}

    ml_probability = _to_float((ml_probability_result or {}).get("ml_probability_pct")) if ml_probability_result else None

    if ml_probability_result and ml_probability_result.get("ok") and ml_probability is not None:
        technical_factors.append(
            f"ML-модель оценила вероятность достижения цели в {int(round(ml_probability))}%."
        )

        internal = assessment.get("internal") or {}
        ml_adjustment = internal.get("ml_adjustment_pct")
        ml_weight = internal.get("ml_weight")

        if ml_adjustment is not None and ml_weight is not None:
            direction = "повысила" if ml_adjustment > 0 else "снизила" if ml_adjustment < 0 else "не изменила"
            technical_factors.append(
                f"ML-корректировка {direction} итоговую вероятность на {abs(float(ml_adjustment)):.1f} п.п.; вес ML: {int(float(ml_weight) * 100)}%."
            )
    elif ml_probability_result and ml_probability_result.get("reason") == "model_not_trained":
        risk_factors.append("ML-модель ещё не обучена, используется базовая вероятностная оценка.")

    if reliability_level:
        risk_factors.append(f"Надёжность прогноза: {reliability_level}.")
    for reason in reliability_reasons[:3]:
        risk_factors.append(str(reason).capitalize() + ".")
    if calibration.get("samples"):
        risk_factors.append(
            f"Историческая проверка похожей цели: {calibration.get('success')} из {calibration.get('samples')} сценариев дошли до цели раньше стопа."
        )
    if liquidity.get("liquidity_bucket") == "low":
        risk_factors.append("Ликвидность ниже комфортной — возможны проскальзывание и резкие движения.")

    return {
        "summary": (
            f"Вероятность {int(probability) if probability is not None else '—'}% рассчитана по технической картине, "
            "исторической проверке достижения цели раньше стопа, ликвидности, объёму, риску сценария и доступным событиям."
        ),
        "technical": technical_factors or ["Технических факторов недостаточно."],
        "news": news_factors,
        "risks": risk_factors or ["Явные риск-факторы не выделены, но прогноз не является гарантией результата."],
    }



def _average(values: list[float]) -> float | None:
    clean = [float(value) for value in values if value is not None]

    if not clean:
        return None

    return sum(clean) / len(clean)


def _stddev(values: list[float]) -> float | None:
    clean = [float(value) for value in values if value is not None]

    if len(clean) < 2:
        return None

    avg = sum(clean) / len(clean)
    variance = sum((value - avg) ** 2 for value in clean) / (len(clean) - 1)

    return variance ** 0.5


def _build_consumer_regime_features(candles: list[dict[str, Any]]) -> dict[str, float | None]:
    """Lightweight regime features for adaptive ML weighting.

    These features intentionally mirror the regime evaluation layer, but are
    computed locally from the latest candle history so consumer scoring does
    not need to rebuild the ML dataset.
    """

    if not candles or len(candles) < 25:
        return {}

    closes = [_to_float(row.get("close")) for row in candles]
    highs = [_to_float(row.get("high")) for row in candles]
    lows = [_to_float(row.get("low")) for row in candles]
    volumes = [_to_float(row.get("volume")) for row in candles]
    values = [_to_float(row.get("value")) for row in candles]

    closes = [value for value in closes if value is not None]

    if len(closes) < 25:
        return {}

    current = closes[-1]

    if current is None or current <= 0:
        return {}

    recent_20 = closes[-20:]
    prev_20 = closes[-40:-20] if len(closes) >= 40 else []

    returns_20: list[float] = []

    for previous, current_close in zip(recent_20[:-1], recent_20[1:]):
        if previous and previous > 0:
            returns_20.append((current_close / previous - 1.0) * 100)

    volatility_20_pct = _stddev(returns_20)

    true_ranges: list[float] = []
    clean_highs = [value for value in highs if value is not None]
    clean_lows = [value for value in lows if value is not None]

    for index in range(max(1, len(candles) - 20), len(candles)):
        high = _to_float(candles[index].get("high"))
        low = _to_float(candles[index].get("low"))
        prev_close = _to_float(candles[index - 1].get("close"))

        if high is None or low is None or prev_close is None:
            continue

        true_ranges.append(
            max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close),
            )
        )

    atr_20 = _average(true_ranges)
    atr_20_pct = (atr_20 / current * 100) if atr_20 is not None and current else None

    recent_high_60 = max(clean_highs[-60:]) if len(clean_highs) >= 5 else None
    recent_low_60 = min(clean_lows[-60:]) if len(clean_lows) >= 5 else None

    if recent_high_60 is not None and recent_low_60 is not None and recent_high_60 > recent_low_60:
        range_position_60_pct = (current - recent_low_60) / (recent_high_60 - recent_low_60) * 100
    else:
        range_position_60_pct = None

    dist_low_60_pct = (
        (current - recent_low_60) / current * 100
        if recent_low_60 is not None and current
        else None
    )

    dist_high_60_pct = (
        (recent_high_60 - current) / current * 100
        if recent_high_60 is not None and current
        else None
    )

    ma_50 = _average(closes[-50:]) if len(closes) >= 50 else None
    ma_50_gap_pct = (
        (current / ma_50 - 1.0) * 100
        if ma_50 is not None and ma_50 > 0
        else None
    )

    ret_20 = (
        (current / closes[-21] - 1.0) * 100
        if len(closes) >= 21 and closes[-21] > 0
        else None
    )

    recent_values = [_to_float(row.get("value")) for row in candles[-20:]]
    previous_values = [_to_float(row.get("value")) for row in candles[-40:-20]]

    recent_value_avg = _average([value for value in recent_values if value is not None])
    previous_value_avg = _average([value for value in previous_values if value is not None])

    value_ratio_20 = (
        recent_value_avg / previous_value_avg
        if recent_value_avg is not None
        and previous_value_avg is not None
        and previous_value_avg > 0
        else None
    )

    return {
        "volatility_20_pct": volatility_20_pct,
        "atr_20_pct": atr_20_pct,
        "range_position_60_pct": range_position_60_pct,
        "dist_low_60_pct": dist_low_60_pct,
        "dist_high_60_pct": dist_high_60_pct,
        "ma_50_gap_pct": ma_50_gap_pct,
        "ret_20": ret_20,
        "value_ratio_20": value_ratio_20,
    }


def _regime_ml_multiplier(regime: dict[str, float | None]) -> tuple[float, str]:
    """Return ML weight multiplier and human-readable regime reason."""

    range_position = regime.get("range_position_60_pct")
    ma_50_gap = regime.get("ma_50_gap_pct")
    ret_20 = regime.get("ret_20")
    value_ratio = regime.get("value_ratio_20")
    dist_low = regime.get("dist_low_60_pct")
    volatility = regime.get("volatility_20_pct")
    atr = regime.get("atr_20_pct")

    strong_reasons: list[str] = []

    if range_position is not None and range_position >= 50:
        strong_reasons.append("цена находится в верхней части 60-дневного диапазона")

    if ma_50_gap is not None and ma_50_gap > 0:
        strong_reasons.append("цена выше MA50")

    if ret_20 is not None and ret_20 > 0:
        strong_reasons.append("20-дневный momentum положительный")

    if value_ratio is not None and value_ratio >= 1.02:
        strong_reasons.append("оборот выше среднего за предыдущий период")

    if dist_low is not None and 2.8 <= dist_low <= 7.7:
        strong_reasons.append("цена не у экстремального минимума, но близко к зоне восстановления")

    cautious_reasons: list[str] = []

    if volatility is not None and volatility <= 0.9:
        cautious_reasons.append("низкая 20-дневная волатильность")

    if atr is not None and atr <= 1.7:
        cautious_reasons.append("низкий ATR")

    if len(strong_reasons) >= 2:
        return 1.18, "regime boost: " + "; ".join(strong_reasons[:3])

    if len(strong_reasons) == 1:
        return 1.08, "regime mild boost: " + strong_reasons[0]

    if cautious_reasons:
        return 0.95, "regime cautious: " + "; ".join(cautious_reasons[:2])

    return 0.90, "regime neutral/unknown: ML не усиливается без подтверждающего режима"

def _adaptive_ml_weight(ml_probability: float | None, regime: dict[str, float | None] | None = None) -> float:
    """
    Evaluation-aware ML weight.

    Текущий threshold-report показал:
    - ML >= 30% даёт небольшой lift к base rate;
    - ML >= 40% исторически работает хуже base rate;
    - вероятности сжаты и не должны трактоваться как агрессивная уверенность.

    Поэтому ML сейчас используется в основном как risk-filter:
    низкий ML сильнее штрафует итоговую вероятность,
    высокий ML почти не бустит сигнал.
    """
    if ml_probability is None:
        return 0.0

    if ml_probability < 25:
        return 0.30

    if ml_probability < 30:
        return 0.24

    if ml_probability < 35:
        return 0.08

    if ml_probability < 40:
        return 0.14

    if ml_probability < 45:
        base_weight = 0.10
    else:
        base_weight = 0.02

    multiplier, _reason = _regime_ml_multiplier(regime or {})
    return round(max(0.02, min(0.18, base_weight * multiplier)), 4)


def _blend_rule_and_ml_probability(
    rule_probability: float | None,
    ml_probability: float | None,
    regime: dict[str, float | None] | None = None,
) -> dict[str, Any]:
    if rule_probability is None and ml_probability is None:
        return {
            "probability": None,
            "source": "none",
            "ml_weight": 0.0,
            "ml_adjustment_pct": None,
        }

    if rule_probability is None:
        return {
            "probability": round(float(ml_probability), 1) if ml_probability is not None else None,
            "source": "ml_only",
            "ml_weight": 1.0,
            "ml_adjustment_pct": None,
        }

    if ml_probability is None:
        return {
            "probability": round(float(rule_probability), 1),
            "source": "rule_only",
            "ml_weight": 0.0,
            "ml_adjustment_pct": 0.0,
        }

    ml_weight = _adaptive_ml_weight(ml_probability, regime=regime)
    rule_weight = 1.0 - ml_weight

    probability = round(rule_probability * rule_weight + ml_probability * ml_weight, 1)

    return {
        "probability": probability,
        "source": "rule_ml_adaptive_blend",
        "ml_weight": round(ml_weight, 2),
        "ml_adjustment_pct": round(probability - rule_probability, 1),
    }


def _consumer_signal_decision_gate(
    probability: float | None,
    reliability_level: str | None,
    risk_level: str | None,
    ml_adjustment_pct: float | None,
    ml_probability_pct: float | None,
    risk_reward_ratio: float | None = None,
    target_distance_pct: float | None = None,
    scenario_direction: str | None = None,
) -> dict[str, Any]:
    probability_value = _to_float(probability)
    ml_adjustment = _to_float(ml_adjustment_pct)
    ml_probability = _to_float(ml_probability_pct)

    reliability = (reliability_level or "").lower()
    risk = (risk_level or "").lower()

    is_high_reliability = "выс" in reliability or "high" in reliability
    is_medium_reliability = "сред" in reliability or "medium" in reliability
    is_high_risk = "high" in risk or "выс" in risk or "risk" in risk or "риск" in risk

    if probability_value is None:
        return {
            "action": "no_forecast",
            "recommendation": "Недостаточно данных",
            "decision": "Прогноз пока не строится",
            "decision_level": "unknown",
            "decision_reason": "Недостаточно данных для расчёта вероятности.",
            "is_buy_candidate": False,
        }

    if is_high_risk and probability_value < 55:
        return {
            "action": "avoid_risk",
            "recommendation": "Не покупать",
            "decision": "Риск превышает ожидаемую доходность",
            "decision_level": "negative",
            "decision_reason": "Сигнал отфильтрован риск-блоком: вероятность недостаточна для текущего уровня риска.",
            "is_buy_candidate": False,
        }

    rr_value = _to_float(risk_reward_ratio)
    target_distance = _to_float(target_distance_pct)
    scenario = str(scenario_direction or "").lower()

    if scenario == "downside" and target_distance is not None and target_distance <= 0:
        return {
            "action": "avoid_downside_signal",
            "recommendation": "Не покупать",
            "decision": "Исходная модель видит downside-сценарий",
            "decision_level": "negative",
            "decision_reason": "Базовый сигнал указывает на цель ниже текущей цены. Для consumer long-сигнала покупка запрещена.",
            "is_buy_candidate": False,
        }

    if target_distance is not None and target_distance <= 0 and probability_value >= 45:
        return {
            "action": "avoid_bad_target",
            "recommendation": "Не покупать",
            "decision": "Некорректная цель для long-сигнала",
            "decision_level": "negative",
            "decision_reason": "Целевая цена не выше текущей цены, поэтому покупка запрещена риск-блоком.",
            "is_buy_candidate": False,
        }

    if rr_value is not None and rr_value < 0.8 and probability_value >= 55:
        return {
            "action": "avoid_bad_rr",
            "recommendation": "Не покупать",
            "decision": "Слабое соотношение цель/риск",
            "decision_level": "negative",
            "decision_reason": "Потенциальная цель слишком мала относительно стопа: risk/reward ниже 0.8. Покупка запрещена риск-блоком.",
            "is_buy_candidate": False,
        }

    if rr_value is not None and 0.8 <= rr_value < 1.2 and probability_value >= 55:
        return {
            "action": "watch_bad_rr",
            "recommendation": "Наблюдать",
            "decision": "Недостаточное соотношение цель/риск",
            "decision_level": "neutral",
            "decision_reason": "Вероятность выглядит приемлемо, но risk/reward ниже 1.2. Покупка не разрешена, инструмент только в наблюдении.",
            "is_buy_candidate": False,
        }

    if ml_probability is not None and ml_probability < 15:
        return {
            "action": "avoid_ml_veto",
            "recommendation": "Не покупать",
            "decision": "ML-veto: модель против сценария",
            "decision_level": "negative",
            "decision_reason": "ML-модель оценивает вероятность достижения цели ниже 15%, поэтому сигнал не может быть покупкой даже при высокой rule-оценке.",
            "is_buy_candidate": False,
        }

    if ml_probability is not None and 15 <= ml_probability < 25 and probability_value >= 45:
        return {
            "action": "watch_ml_rejected",
            "recommendation": "Наблюдать",
            "decision": "Rule-сигнал есть, но ML не подтверждает покупку",
            "decision_level": "neutral",
            "decision_reason": "ML-модель оценивает вероятность достижения цели в зоне 15–25%, поэтому покупка запрещена; инструмент можно оставить только в наблюдении.",
            "is_buy_candidate": False,
        }

    if ml_adjustment is not None and ml_adjustment <= -10 and probability_value < 45:
        return {
            "action": "avoid_ml_filter",
            "recommendation": "Не покупать",
            "decision": "ML-фильтр снизил прогноз",
            "decision_level": "negative",
            "decision_reason": "ML-модель заметно снизила итоговую вероятность, поэтому сигнал не проходит потребительский фильтр.",
            "is_buy_candidate": False,
        }

    if probability_value >= 65 and is_high_reliability:
        return {
            "action": "buy",
            "recommendation": "Покупать",
            "decision": "Сильный сигнал",
            "decision_level": "positive",
            "decision_reason": "Вероятность высокая, надёжность достаточная, риск-фильтр пройден.",
            "is_buy_candidate": True,
        }

    if probability_value >= 58 and (is_high_reliability or is_medium_reliability):
        return {
            "action": "consider_buy",
            "recommendation": "Рассмотреть покупку",
            "decision": "Умеренно положительный сигнал",
            "decision_level": "positive",
            "decision_reason": "Вероятность выше среднего, но сигнал требует контроля риска и размера позиции.",
            "is_buy_candidate": True,
        }

    if probability_value >= 45:
        return {
            "action": "watch",
            "recommendation": "Наблюдать",
            "decision": "Нейтральный сигнал",
            "decision_level": "neutral",
            "decision_reason": "Вероятность недостаточна для покупки, но инструмент стоит оставить в наблюдении.",
            "is_buy_candidate": False,
        }

    if ml_probability is not None and 35 <= ml_probability < 45 and probability_value >= 40:
        return {
            "action": "watch_ml_confirmed",
            "recommendation": "Наблюдать",
            "decision": "Есть ML-подтверждение, но итоговая вероятность пока низкая",
            "decision_level": "neutral",
            "decision_reason": "ML находится в рабочей зоне 35–45%, где walk-forward validation показал стабильный lift, но итоговый consumer score ещё не дотягивает до покупки.",
            "is_buy_candidate": False,
        }

    return {
        "action": "avoid",
        "recommendation": "Не покупать",
        "decision": "Слабый сигнал",
        "decision_level": "negative",
        "decision_reason": "Итоговая вероятность ниже минимального порога для потребительского сигнала.",
        "is_buy_candidate": False,
    }




def _infer_source_scenario_direction(
    signal: dict[str, Any],
    price: float | None,
) -> tuple[str, str]:
    source_action = str(signal.get("action") or "").strip()
    source_target = _to_float(signal.get("target_price"))

    if source_action == "risk_sell_watch":
        return "downside", "Исходная модель пометила сигнал как risk/downside."

    if price is not None and price > 0 and source_target is not None:
        if source_target < price:
            return "downside", "Исходная целевая цена ниже текущей цены."
        if source_target > price:
            return "long", "Исходная целевая цена выше текущей цены."

    if source_action in {"buy_watch", "watch_buy"}:
        return "long", "Исходная модель допускает long-сценарий."

    return "neutral", "Направление исходного сценария не определено."

def _build_position_sizing(
    *,
    action: str | None,
    price: float | None,
    target_price: float | None,
    stop_loss: float | None,
    probability: float | None,
    risk_level: str | None,
    reliability_level: str | None,
    reliability_score: float | None,
    ml_probability: float | None,
    ml_regime_multiplier: float | None,
    volatility_pct: float | None,
) -> dict[str, Any]:
    """Risk-adjusted position sizing for consumer signals.

    This is not portfolio optimization. It is a conservative risk layer that
    limits position size based on action quality, stop distance, reliability,
    ML confirmation and volatility.
    """

    normalized_action = str(action or "").strip()
    risk_text = str(risk_level or "").lower()
    reliability_text = str(reliability_level or "").lower()

    no_entry_actions = {
        "avoid",
        "avoid_ml_filter",
        "avoid_ml_veto",
        "avoid_risk",
        "no_forecast",
        "no_data",
        "no_price",
        "watch",
        "watch_ml_confirmed",
        "watch_ml_rejected",
    }

    if normalized_action in no_entry_actions:
        return {
            "allowed": False,
            "position_action": "no_entry" if normalized_action.startswith("avoid") else "watch_only",
            "max_position_pct": 0.0,
            "risk_per_trade_pct": 0.0,
            "stop_loss": _round(stop_loss),
            "stop_distance_pct": None,
            "target_price": _round(target_price),
            "target_distance_pct": _round(_pct_change(target_price, price)),
            "risk_reward_ratio": None,
            "reason": "Вход запрещён или разрешено только наблюдение по текущему consumer decision gate.",
            "risk_flags": [f"action={normalized_action}"],
        }

    if normalized_action == "buy":
        base_position_pct = 6.0
        base_risk_pct = 1.0
        position_action = "buy"
    elif normalized_action == "consider_buy":
        base_position_pct = 3.5
        base_risk_pct = 0.65
        position_action = "starter_position"
    else:
        return {
            "allowed": False,
            "position_action": "watch_only",
            "max_position_pct": 0.0,
            "risk_per_trade_pct": 0.0,
            "stop_loss": _round(stop_loss),
            "stop_distance_pct": None,
            "target_price": _round(target_price),
            "target_distance_pct": _round(_pct_change(target_price, price)),
            "risk_reward_ratio": None,
            "reason": "Для текущего действия позиция не открывается.",
            "risk_flags": [f"action={normalized_action}"],
        }

    risk_flags: list[str] = []
    factor = 1.0

    if "выс" in risk_text or "high" in risk_text or "risk" in risk_text or "риск" in risk_text:
        factor *= 0.55
        risk_flags.append("высокий риск сценария")
    elif "сред" in risk_text or "medium" in risk_text:
        factor *= 0.85
        risk_flags.append("средний риск сценария")

    if "низ" in reliability_text or "low" in reliability_text:
        factor *= 0.60
        risk_flags.append("низкая надёжность прогноза")
    elif "выс" in reliability_text or "high" in reliability_text:
        factor *= 1.08

    score = _to_float(reliability_score)
    if score is not None:
        if score < 45:
            factor *= 0.65
            risk_flags.append("низкий reliability_score")
        elif score >= 75:
            factor *= 1.05

    ml_value = _to_float(ml_probability)
    if ml_value is not None:
        if ml_value < 25:
            factor *= 0.50
            risk_flags.append("ML ниже 25%")
        elif ml_value < 35:
            factor *= 0.80
            risk_flags.append("ML не даёт полноценного подтверждения")
        elif 35 <= ml_value < 45:
            factor *= 1.05
        else:
            factor *= 0.95

    regime = _to_float(ml_regime_multiplier)
    if regime is not None:
        if regime >= 1.15:
            factor *= 1.08
        elif regime < 1.0:
            factor *= 0.90
            risk_flags.append("режим не усиливает ML")

    vol = _to_float(volatility_pct)
    if vol is not None:
        if vol >= 4.0:
            factor *= 0.60
            risk_flags.append("повышенная волатильность")
        elif vol >= 2.8:
            factor *= 0.80
            risk_flags.append("умеренно высокая волатильность")

    derived_stop = False
    stop_value = _to_float(stop_loss)

    if price is not None and price > 0 and (stop_value is None or stop_value >= price):
        default_stop_pct = min(max((vol or 2.0) * 1.8, 2.5), 8.0)
        stop_value = price * (1 - default_stop_pct / 100)
        derived_stop = True
        risk_flags.append("стоп рассчитан автоматически")

    stop_distance_pct = None
    target_distance_pct = _pct_change(target_price, price)
    risk_reward_ratio = None

    if price is not None and price > 0 and stop_value is not None and stop_value < price:
        stop_distance_pct = (price - stop_value) / price * 100

    if (
        stop_distance_pct is not None
        and stop_distance_pct > 0
        and target_distance_pct is not None
        and target_distance_pct > 0
    ):
        risk_reward_ratio = target_distance_pct / stop_distance_pct

        if risk_reward_ratio < 0.8:
            factor *= 0.45
            risk_flags.append("слабое соотношение цель/риск")
        elif risk_reward_ratio < 1.2:
            factor *= 0.70
            risk_flags.append("умеренное соотношение цель/риск")
        elif risk_reward_ratio >= 2.0:
            factor *= 1.08

    position_cap_pct = base_position_pct * factor
    risk_per_trade_pct = base_risk_pct * min(factor, 1.0)

    if stop_distance_pct is not None and stop_distance_pct > 0:
        max_by_risk_pct = risk_per_trade_pct / stop_distance_pct * 100
        position_cap_pct = min(position_cap_pct, max_by_risk_pct)

    position_cap_pct = max(0.25, min(position_cap_pct, 7.0))
    risk_per_trade_pct = max(0.10, min(risk_per_trade_pct, 1.0))

    reason_parts = [
        f"Базовый режим: {position_action}.",
        f"Размер позиции ограничен до {position_cap_pct:.2f}% портфеля.",
        f"Риск на сделку: {risk_per_trade_pct:.2f}% портфеля.",
    ]

    if risk_flags:
        reason_parts.append("Факторы снижения: " + "; ".join(risk_flags[:5]) + ".")

    return {
        "allowed": True,
        "position_action": position_action,
        "max_position_pct": _round(position_cap_pct, 2),
        "risk_per_trade_pct": _round(risk_per_trade_pct, 2),
        "stop_loss": _round(stop_value),
        "stop_source": "derived" if derived_stop else "signal",
        "stop_distance_pct": _round(stop_distance_pct, 2),
        "target_price": _round(target_price),
        "target_distance_pct": _round(target_distance_pct, 2),
        "risk_reward_ratio": _round(risk_reward_ratio, 2),
        "reason": " ".join(reason_parts),
        "risk_flags": risk_flags,
    }

def build_consumer_forecast(
    ticker: str,
    instrument: dict[str, Any],
    latest: dict[str, Any],
    technical: dict[str, Any],
    candles: list[dict[str, Any]],
    signal: dict[str, Any],
    events: list[dict[str, Any]],
    global_events: list[dict[str, Any]] | None = None,
    ml_probability_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    price = _to_float(latest.get("close"))
    regime_features = _build_consumer_regime_features(candles)
    source_signal_action = signal.get("action")
    source_signal_type = signal.get("signal_type")
    source_target_price = _to_float(signal.get("target_price"))
    scenario_direction, scenario_reason = _infer_source_scenario_direction(signal, price)
    global_events = global_events or []
    target_price = _derive_target_price(price, signal, technical)
    forecast_range = _derive_forecast_range(price, target_price, signal, technical)
    stop_loss_value = _to_float(signal.get("stop_loss"))
    rule_probability = _calculate_target_probability(signal, technical, price, target_price, events)
    news_assessment = _build_news_assessment(
        events=events,
        scenario_direction=scenario_direction,
    )
    news_assessment = _apply_news_relevance_scoring(
        news_assessment=news_assessment,
        events=events,
        ticker=str((instrument or {}).get("ticker") or ""),
        instrument=instrument,
    )
    global_news_assessment = _build_global_event_assessment(
        events=global_events,
        ticker=str((instrument or {}).get("ticker") or ticker or ""),
        instrument=instrument,
        scenario_direction=scenario_direction,
    )
    ml_probability = (
        _to_float((ml_probability_result or {}).get("ml_probability_pct"))
        if ml_probability_result and ml_probability_result.get("ok")
        else None
    )

    probability_blend = _blend_rule_and_ml_probability(
        rule_probability=rule_probability,
        ml_probability=ml_probability,
        regime=regime_features,
    )
    base_probability = probability_blend.get("probability")
    probability_source = probability_blend.get("source")
    ml_weight = probability_blend.get("ml_weight")
    ml_adjustment_pct = probability_blend.get("ml_adjustment_pct")
    regime_multiplier, regime_reason = _regime_ml_multiplier(regime_features)

    probability_assessment = build_probability_assessment(
        base_probability_pct=base_probability,
        candles=candles,
        signal=signal,
        technical=technical,
        price=price,
        target_price=target_price,
        stop_loss=stop_loss_value,
        events=events,
        horizon_days=20,
    )
    base_probability = probability_assessment.get("probability_pct")
    ticker_news_adjustment_pct = _to_float(news_assessment.get("adjustment_pct")) or 0.0
    global_event_adjustment_pct = _to_float(global_news_assessment.get("adjustment_pct")) or 0.0
    news_adjustment_pct = _round(
        _clamp(ticker_news_adjustment_pct + global_event_adjustment_pct, -10.0, 10.0),
        1,
    )

    probability = _round(_clamp(float(base_probability or 0) + news_adjustment_pct, 1, 99), 0)

    news_assessment["ticker_news_adjustment_pct"] = _round(ticker_news_adjustment_pct, 1)
    news_assessment["global_event_adjustment_pct"] = _round(global_event_adjustment_pct, 1)
    news_assessment["adjustment_pct"] = news_adjustment_pct
    news_assessment["global_news_assessment"] = global_news_assessment

    if global_news_assessment.get("has_global_events"):
        news_assessment["summary"] = (
            str(news_assessment.get("summary") or "").strip()
            + " "
            + str(global_news_assessment.get("reason") or "").strip()
        ).strip()

    probability_assessment["probability_pct"] = probability
    probability_assessment.setdefault("internal", {})
    probability_assessment["internal"]["pre_news_probability_pct"] = _round(base_probability, 0)
    probability_assessment["internal"]["news_adjustment_pct"] = _round(news_adjustment_pct, 1)
    probability_assessment["internal"]["ticker_news_adjustment_pct"] = _round(ticker_news_adjustment_pct, 1)
    probability_assessment["internal"]["global_event_adjustment_pct"] = _round(global_event_adjustment_pct, 1)
    probability_assessment["internal"]["news_assessment"] = news_assessment
    probability_assessment["internal"]["global_news_assessment"] = global_news_assessment

    preliminary_target_distance_pct = _pct_change(target_price, price)
    preliminary_stop_distance_pct = None

    if price is not None and price > 0 and stop_loss_value is not None and stop_loss_value < price:
        preliminary_stop_distance_pct = (price - stop_loss_value) / price * 100

    preliminary_risk_reward_ratio = (
        preliminary_target_distance_pct / preliminary_stop_distance_pct
        if preliminary_target_distance_pct is not None
        and preliminary_target_distance_pct > 0
        and preliminary_stop_distance_pct is not None
        and preliminary_stop_distance_pct > 0
        else None
    )

    decision_gate = _consumer_signal_decision_gate(
        probability=probability,
        reliability_level=probability_assessment.get("reliability_level"),
        risk_level=signal.get("risk_level"),
        ml_adjustment_pct=ml_adjustment_pct,
        ml_probability_pct=ml_probability,
        risk_reward_ratio=preliminary_risk_reward_ratio,
        target_distance_pct=preliminary_target_distance_pct,
        scenario_direction=scenario_direction,
    )
    recommendation, tone = _recommendation_from_action(signal.get("action"), probability)

    potential_pct = _round(_pct_change(target_price, price))
    potential_abs = _round(target_price - price) if price is not None and target_price is not None else None

    if signal.get("action") == "risk_sell_watch":
        forecast_price = forecast_range.get("low") or target_price
    elif signal.get("action") in {"buy_watch", "watch_buy"}:
        forecast_price = target_price
    else:
        high = _to_float(forecast_range.get("high"))
        low = _to_float(forecast_range.get("low"))
        forecast_price = _round((high + low) / 2) if high is not None and low is not None else target_price

    position_sizing = _build_position_sizing(
        action=decision_gate.get("action"),
        price=price,
        target_price=target_price,
        stop_loss=stop_loss_value,
        probability=probability,
        risk_level=signal.get("risk_level"),
        reliability_level=probability_assessment.get("reliability_level"),
        reliability_score=probability_assessment.get("reliability_score"),
        ml_probability=ml_probability,
        ml_regime_multiplier=regime_multiplier,
        volatility_pct=_to_float(technical.get("volatility_20d_pct")),
    )

    # Preserve RR diagnostics even when entry is blocked by decision gate.
    if preliminary_target_distance_pct is not None and position_sizing.get("target_distance_pct") is None:
        position_sizing["target_distance_pct"] = _round(preliminary_target_distance_pct, 2)

    if preliminary_stop_distance_pct is not None and position_sizing.get("stop_distance_pct") is None:
        position_sizing["stop_distance_pct"] = _round(preliminary_stop_distance_pct, 2)

    if preliminary_risk_reward_ratio is not None and position_sizing.get("risk_reward_ratio") is None:
        position_sizing["risk_reward_ratio"] = _round(preliminary_risk_reward_ratio, 2)

    return {
        "ticker": ticker,
        "name": instrument.get("name") or ticker,
        "sector": instrument.get("sector"),
        "asset_type": instrument.get("asset_type"),
        "is_signal_eligible": instrument.get("is_signal_eligible"),
        "price": _round(price),
        "trade_date": latest.get("trade_date"),
        "recommendation": decision_gate.get("recommendation") or recommendation,
        "decision": decision_gate.get("decision"),
        "decision_level": decision_gate.get("decision_level"),
        "decision_reason": decision_gate.get("decision_reason"),
        "is_buy_candidate": decision_gate.get("is_buy_candidate"),
        "recommendation_tone": tone,
        "action": decision_gate.get("action") or signal.get("action"),
        "target_price": _round(target_price),
        "forecast_price": _round(forecast_price),
        "forecast_range": forecast_range,
        "potential_abs": potential_abs,
        "potential_pct": potential_pct,
        "target_probability_pct": probability,
        "base_probability_pct": probability_assessment.get("base_probability_pct"),
        "rule_probability_pct": _round(rule_probability, 1),
        "ml_probability_pct": _round(ml_probability, 1),
        "ml_weight": ml_weight,
        "ml_adjustment_pct": ml_adjustment_pct,
        "probability_source": f"{probability_source}_news" if news_assessment.get("has_events") else probability_source,
        "news_adjustment_pct": _round(news_adjustment_pct, 1),
        "ticker_news_adjustment_pct": _round(ticker_news_adjustment_pct, 1),
        "global_event_adjustment_pct": _round(global_event_adjustment_pct, 1),
        "global_news_assessment": global_news_assessment,
        "global_event_tags": global_news_assessment.get("tags") or [],
        "global_event_reason": global_news_assessment.get("reason"),
        "macro_regime_flags": global_news_assessment.get("macro_regime_flags") or [],
        "news_effect": news_assessment.get("news_effect"),
        "news_relevance_score": news_assessment.get("ticker_relevance_score"),
        "news_source_reliability_score": news_assessment.get("source_reliability_score"),
        "news_event_scope": news_assessment.get("event_scope"),
        "news_assessment": news_assessment,
        "news_risk_flags": news_assessment.get("risk_flags") or [],
        "ml_regime_multiplier": regime_multiplier,
        "ml_regime_reason": regime_reason,
        "source_signal_action": source_signal_action,
        "source_signal_type": source_signal_type,
        "source_target_price": _round(source_target_price),
        "scenario_direction": scenario_direction,
        "scenario_reason": scenario_reason,
        "consumer_action": decision_gate.get("action"),
        "recommendation": decision_gate.get("recommendation"),
        "decision": decision_gate.get("decision"),
        "decision_level": decision_gate.get("decision_level"),
        "decision_reason": decision_gate.get("decision_reason"),
        "is_buy_candidate": decision_gate.get("is_buy_candidate"),
        "horizon": signal.get("horizon") or "1–4 недели",
        "risk_level": signal.get("risk_level"),
        "reliability_level": probability_assessment.get("reliability_level"),
        "reliability_score": probability_assessment.get("reliability_score"),
        "stop_loss": _round(position_sizing.get("stop_loss")),
        "position_sizing": position_sizing,
        "risk_reward_ratio": position_sizing.get("risk_reward_ratio"),
        "explanation": _build_explanation(
            signal,
            technical,
            events,
            probability,
            probability_assessment,
            ml_probability_result=ml_probability_result,
        ),
        "probability_assessment": probability_assessment,
        "events": events,
        "internal": {
            "engine": CONSUMER_SIGNAL_MODEL_VERSION,
            "confidence_pct": _round(signal.get("confidence_pct"), 0),
            "quality_score": _round(signal.get("quality_score"), 0),
            "risk_reward_ratio": _round(signal.get("risk_reward_ratio"), 2),
            "source_signal_action": source_signal_action,
            "source_signal_type": source_signal_type,
            "source_target_price": _round(source_target_price),
            "scenario_direction": scenario_direction,
            "scenario_reason": scenario_reason,
        },
    }



def _instrument_to_consumer_dict(instrument: Instrument | None, ticker: str) -> dict[str, Any]:
    if instrument is None:
        return {
            "ticker": ticker,
            "name": ticker,
            "asset_type": "unknown",
            "is_signal_eligible": False,
        }

    return {
        "ticker": instrument.ticker,
        "name": instrument.name or instrument.ticker,
        "board": instrument.board,
        "sector": instrument.sector,
        "asset_type": getattr(instrument, "asset_type", "unknown") or "unknown",
        "is_signal_eligible": bool(getattr(instrument, "is_signal_eligible", False)),
        "lot_size": instrument.lot_size,
    }


def _unsupported_forecast_response(
    ticker: str,
    instrument: dict[str, Any],
    reason: str,
    message: str,
) -> dict[str, Any]:
    return {
        "ok": False,
        "ticker": ticker,
        "reason": reason,
        "message": message,
        "instrument": instrument,
        "forecast": None,
        "signal": {
            "recommendation": "Недостаточно данных",
            "target_probability_pct": None,
            "target_price": None,
            "forecast_range": {"low": None, "high": None},
            "horizon": None,
            "risk_level": "unknown",
            "reliability_level": "Низкая",
            "reliability_score": 0,
            "explanation": {
                "summary": message,
                "technical": ["Прогноз не построен, потому что инструмент не проходит базовые условия модели."],
                "news": ["Новостной фон не анализировался для неподдерживаемого прогноза."],
                "risks": ["Система не должна выдавать вероятность там, где модель неприменима или данных недостаточно."],
            },
        },
    }


def _get_consumer_instrument(db: Session, ticker: str) -> Instrument | None:
    return db.scalar(select(Instrument).where(Instrument.ticker == ticker))


def _get_candles_count(db: Session, ticker: str) -> int:
    return int(db.scalar(select(func.count(Candle.id)).where(Candle.ticker == ticker)) or 0)


def build_consumer_signal_for_ticker(
    db: Session,
    ticker: str,
    candles_limit: int = 240,
) -> dict[str, Any]:
    ticker = ticker.upper().strip()

    db_instrument = _get_consumer_instrument(db=db, ticker=ticker)
    instrument_meta = _instrument_to_consumer_dict(db_instrument, ticker)

    if db_instrument is None:
        return _unsupported_forecast_response(
            ticker=ticker,
            instrument=instrument_meta,
            reason="instrument_not_found",
            message="Инструмент не найден в локальном справочнике MOEX. Обновите universe или проверьте тикер.",
        )

    if not instrument_meta.get("is_signal_eligible"):
        asset_type = instrument_meta.get("asset_type") or "unknown"
        return _unsupported_forecast_response(
            ticker=ticker,
            instrument=instrument_meta,
            reason="unsupported_asset_type",
            message=f"Для типа инструмента '{asset_type}' потребительский прогноз пока не строится.",
        )

    candles_count = _get_candles_count(db=db, ticker=ticker)
    if candles_count < 60:
        return _unsupported_forecast_response(
            ticker=ticker,
            instrument=instrument_meta,
            reason="not_enough_candles",
            message=f"Недостаточно исторических данных для прогноза: найдено {candles_count} свечей, нужно минимум 60.",
        )

    snapshot = get_ticker_snapshot(
        db=db,
        ticker=ticker,
        limit=candles_limit,
    )

    latest = snapshot.get("latest") or {}
    technical = snapshot.get("technical") or {}
    fallback_signal = snapshot.get("signal") or {}
    instrument = {
        **instrument_meta,
        **(snapshot.get("instrument") or {"ticker": ticker, "name": ticker}),
        "asset_type": instrument_meta.get("asset_type"),
        "is_signal_eligible": instrument_meta.get("is_signal_eligible"),
    }
    candles = snapshot.get("candles") or []

    # Дополняем технический блок ближайшими максимумами/минимумами, чтобы прогноз имел диапазон.
    recent = candles[-20:] if candles else []
    highs = [_to_float(row.get("high")) for row in recent]
    lows = [_to_float(row.get("low")) for row in recent]
    highs = [value for value in highs if value is not None]
    lows = [value for value in lows if value is not None]
    technical = dict(technical)
    if highs and technical.get("recent_high") is None:
        technical["recent_high"] = round(max(highs), 2)
    if lows and technical.get("recent_low") is None:
        technical["recent_low"] = round(min(lows), 2)

    signal = _build_unified_signal(
        candles=candles,
        latest=latest,
        technical=technical,
        fallback_signal=fallback_signal,
    )

    related_events = list_related_events(db=db, ticker=ticker, limit=3)
    global_events = list_global_market_events(db=db, limit=12)
    events = _merge_events(related_events, global_events)

    try:
        ml_probability_result = predict_ml_probability_for_ticker(
            db=db,
            ticker=ticker,
            min_history=60,
        )
    except Exception as exc:  # noqa: BLE001
        ml_probability_result = {
            "ok": False,
            "reason": "ml_prediction_error",
            "message": str(exc),
        }

    forecast = build_consumer_forecast(
        ticker=ticker,
        instrument=instrument,
        latest=latest,
        technical=technical,
        candles=candles,
        signal=signal,
        events=related_events,
        global_events=global_events,
        ml_probability_result=ml_probability_result,
    )

    return {
        "ok": True,
        "ticker": ticker,
        "events": events,
        "related_events": related_events,
        "global_events": global_events,
        "forecast": forecast,
        "signal": {
            "recommendation": forecast.get("recommendation"),
            "target_probability_pct": forecast.get("target_probability_pct"),
            "rule_probability_pct": forecast.get("rule_probability_pct"),
            "ml_probability_pct": forecast.get("ml_probability_pct"),
            "ml_weight": forecast.get("ml_weight"),
            "ml_adjustment_pct": forecast.get("ml_adjustment_pct"),
            "ml_regime_multiplier": forecast.get("ml_regime_multiplier"),
            "ml_regime_reason": forecast.get("ml_regime_reason"),
            "probability_source": forecast.get("probability_source"),
            "news_adjustment_pct": forecast.get("news_adjustment_pct"),
            "ticker_news_adjustment_pct": forecast.get("ticker_news_adjustment_pct"),
            "global_event_adjustment_pct": forecast.get("global_event_adjustment_pct"),
            "global_news_assessment": forecast.get("global_news_assessment"),
            "global_event_tags": forecast.get("global_event_tags"),
            "global_event_reason": forecast.get("global_event_reason"),
            "macro_regime_flags": forecast.get("macro_regime_flags"),
            "news_effect": forecast.get("news_effect"),
            "news_relevance_score": forecast.get("news_relevance_score"),
            "news_source_reliability_score": forecast.get("news_source_reliability_score"),
            "news_event_scope": forecast.get("news_event_scope"),
            "news_assessment": forecast.get("news_assessment"),
            "news_risk_flags": forecast.get("news_risk_flags"),
            "source_signal_action": forecast.get("source_signal_action"),
            "source_signal_type": forecast.get("source_signal_type"),
            "source_target_price": forecast.get("source_target_price"),
            "scenario_direction": forecast.get("scenario_direction"),
            "scenario_reason": forecast.get("scenario_reason"),
            "consumer_action": forecast.get("consumer_action"),
            "recommendation": forecast.get("recommendation"),
            "decision": forecast.get("decision"),
            "decision_level": forecast.get("decision_level"),
            "decision_reason": forecast.get("decision_reason"),
            "is_buy_candidate": forecast.get("is_buy_candidate"),
            "target_price": forecast.get("target_price"),
            "forecast_range": forecast.get("forecast_range"),
            "horizon": forecast.get("horizon"),
            "risk_level": forecast.get("risk_level"),
            "reliability_level": forecast.get("reliability_level"),
            "reliability_score": forecast.get("reliability_score"),
            "position_sizing": forecast.get("position_sizing"),
            "risk_reward_ratio": forecast.get("risk_reward_ratio"),
            "probability_assessment": forecast.get("probability_assessment"),
            "explanation": forecast.get("explanation"),
        },
    }


def list_consumer_signals(
    db: Session,
    limit: int = 100,
    action: str | None = None,
    min_probability: float | None = None,
    candles_limit: int = 240,
    q: str | None = None,
    scenario: str = "all",
    news: str = "all",
) -> dict[str, Any]:
    from app.services.market_universe import search_instruments

    query_text = (q or "").strip()
    scenario_filter = (scenario or "all").strip().lower()
    news_filter = (news or "all").strip().lower()

    if scenario_filter not in {"all", "long", "downside", "neutral"}:
        scenario_filter = "all"

    if news_filter not in {"all", "with_events", "no_events", "boost", "penalty", "veto", "info_only"}:
        news_filter = "all"

    def _matches_scenario_filter(forecast: dict[str, Any]) -> bool:
        if scenario_filter == "all":
            return True

        direction = str(forecast.get("scenario_direction") or "neutral").lower()
        action_value = str(forecast.get("action") or "")

        if scenario_filter == "downside":
            return direction == "downside" or action_value == "avoid_downside_signal"

        if scenario_filter == "long":
            return direction in {"long", "neutral"} and action_value != "avoid_downside_signal"

        if scenario_filter == "neutral":
            return direction == "neutral"

        return True

    def _matches_news_filter(forecast: dict[str, Any]) -> bool:
        if news_filter == "all":
            return True

        news_assessment = forecast.get("news_assessment") or {}
        has_events = bool(news_assessment.get("has_events"))
        effect = str(forecast.get("news_effect") or news_assessment.get("news_effect") or "none").lower()

        if news_filter == "with_events":
            return has_events

        if news_filter == "no_events":
            return not has_events

        return has_events and effect == news_filter

    search_result = search_instruments(
        db=db,
        q=query_text or None,
        limit=limit,
        only_with_candles=True,
        eligible_only=True,
    )
    tickers = [row.get("ticker") for row in search_result.get("rows") or [] if row.get("ticker")]
    rows: list[dict[str, Any]] = []

    for ticker in tickers:
        data = build_consumer_signal_for_ticker(
            db=db,
            ticker=ticker,
            candles_limit=candles_limit,
        )
        if not data.get("ok"):
            continue

        forecast = data.get("forecast") or {}

        if not _matches_scenario_filter(forecast):
            continue

        if not _matches_news_filter(forecast):
            continue

        if action and forecast.get("action") != action:
            continue

        probability = _to_float(forecast.get("target_probability_pct"))
        if min_probability is not None and (probability is None or probability < min_probability):
            continue

        rows.append(
            {
                "ticker": ticker,
                "name": forecast.get("name") or ticker,
                "price": forecast.get("price"),
                "trade_date": forecast.get("trade_date"),
                "recommendation": forecast.get("recommendation"),
                "recommendation_tone": forecast.get("recommendation_tone"),
                "action": forecast.get("action"),
                "consumer_action": forecast.get("consumer_action"),
                "decision": forecast.get("decision"),
                "decision_level": forecast.get("decision_level"),
                "decision_reason": forecast.get("decision_reason"),
                "is_buy_candidate": forecast.get("is_buy_candidate"),
                "target_probability_pct": forecast.get("target_probability_pct"),
                "rule_probability_pct": forecast.get("rule_probability_pct"),
                "ml_probability_pct": forecast.get("ml_probability_pct"),
                "ml_weight": forecast.get("ml_weight"),
                "ml_adjustment_pct": forecast.get("ml_adjustment_pct"),
                "ml_regime_multiplier": forecast.get("ml_regime_multiplier"),
                "ml_regime_reason": forecast.get("ml_regime_reason"),
                "probability_source": forecast.get("probability_source"),
            "news_adjustment_pct": forecast.get("news_adjustment_pct"),
            "ticker_news_adjustment_pct": forecast.get("ticker_news_adjustment_pct"),
            "global_event_adjustment_pct": forecast.get("global_event_adjustment_pct"),
            "global_news_assessment": forecast.get("global_news_assessment"),
            "global_event_tags": forecast.get("global_event_tags"),
            "global_event_reason": forecast.get("global_event_reason"),
            "macro_regime_flags": forecast.get("macro_regime_flags"),
            "news_effect": forecast.get("news_effect"),
            "news_relevance_score": forecast.get("news_relevance_score"),
            "news_source_reliability_score": forecast.get("news_source_reliability_score"),
            "news_event_scope": forecast.get("news_event_scope"),
            "news_assessment": forecast.get("news_assessment"),
            "news_risk_flags": forecast.get("news_risk_flags"),
                "source_signal_action": forecast.get("source_signal_action"),
                "source_signal_type": forecast.get("source_signal_type"),
                "source_target_price": forecast.get("source_target_price"),
                "scenario_direction": forecast.get("scenario_direction"),
                "scenario_reason": forecast.get("scenario_reason"),
                "target_price": forecast.get("target_price"),
                "forecast_price": forecast.get("forecast_price"),
                "forecast_range": forecast.get("forecast_range"),
                "potential_abs": forecast.get("potential_abs"),
                "potential_pct": forecast.get("potential_pct"),
                "horizon": forecast.get("horizon"),
                "risk_level": forecast.get("risk_level"),
                "reliability_level": forecast.get("reliability_level"),
                "reliability_score": forecast.get("reliability_score"),
                "position_sizing": forecast.get("position_sizing"),
                "risk_reward_ratio": forecast.get("risk_reward_ratio"),
                "explanation": forecast.get("explanation"),
                "ticker_url": f"/tickers/{ticker}",
            }
        )

    rows.sort(
        key=lambda row: (
            ACTION_RANK.get(row.get("action"), 99),
            -float(row.get("target_probability_pct") or 0),
            row.get("ticker") or "",
        )
    )

    positive_actions = {"buy", "consider_buy", "buy_watch", "watch_buy"}
    watch_actions = {"watch", "watch_ml_confirmed", "watch_ml_rejected", "watch_bad_rr", "hold_watch"}
    risk_actions = {"avoid", "avoid_downside_signal", "avoid_bad_target", "avoid_bad_rr", "avoid_ml_filter", "avoid_ml_veto", "avoid_risk", "risk_sell_watch"}

    scenario_counts = {
        "long": sum(1 for row in rows if row.get("scenario_direction") == "long"),
        "downside": sum(1 for row in rows if row.get("scenario_direction") == "downside"),
        "neutral": sum(1 for row in rows if row.get("scenario_direction") == "neutral"),
        "unknown": sum(1 for row in rows if not row.get("scenario_direction")),
    }

    news_counts = {
        "with_events": sum(1 for row in rows if (row.get("news_assessment") or {}).get("has_events")),
        "no_events": sum(1 for row in rows if not (row.get("news_assessment") or {}).get("has_events")),
        "boost": sum(1 for row in rows if row.get("news_effect") == "boost"),
        "penalty": sum(1 for row in rows if row.get("news_effect") == "penalty"),
        "veto": sum(1 for row in rows if row.get("news_effect") == "veto"),
        "info_only": sum(1 for row in rows if row.get("news_effect") == "info_only"),
    }

    top_global_tags: dict[str, int] = {}
    for row in rows:
        for tag in row.get("global_event_tags") or []:
            tag_text = str(tag or "").strip()
            if tag_text:
                top_global_tags[tag_text] = top_global_tags.get(tag_text, 0) + 1

    global_event_counts = {
        "with_global_events": sum(
            1 for row in rows if (row.get("global_news_assessment") or {}).get("has_global_events")
        ),
        "positive_adjustment": sum(1 for row in rows if (_to_float(row.get("global_event_adjustment_pct")) or 0) > 0),
        "negative_adjustment": sum(1 for row in rows if (_to_float(row.get("global_event_adjustment_pct")) or 0) < 0),
        "neutral_adjustment": sum(1 for row in rows if (_to_float(row.get("global_event_adjustment_pct")) or 0) == 0),
        "top_tags": dict(sorted(top_global_tags.items(), key=lambda item: (-item[1], item[0]))[:12]),
    }

    summary = {
        "total": len(rows),
        "scenario_filter": scenario_filter,
        "scenario_counts": scenario_counts,
        "news_filter": news_filter,
        "news_counts": news_counts,
        "global_event_counts": global_event_counts,
        "positive": sum(1 for row in rows if row.get("action") in positive_actions),
        "watch": sum(1 for row in rows if row.get("action") in watch_actions),
        "risk": sum(1 for row in rows if row.get("action") in risk_actions),
        "buy": sum(1 for row in rows if row.get("action") == "buy"),
        "consider_buy": sum(1 for row in rows if row.get("action") == "consider_buy"),
        "watch_ml_confirmed": sum(1 for row in rows if row.get("action") == "watch_ml_confirmed"),
        "avoid_ml_filter": sum(1 for row in rows if row.get("action") == "avoid_ml_filter"),
        "avoid_ml_veto": sum(1 for row in rows if row.get("action") == "avoid_ml_veto"),
        "avoid_downside_signal": sum(1 for row in rows if row.get("action") == "avoid_downside_signal"),
        "avoid_bad_target": sum(1 for row in rows if row.get("action") == "avoid_bad_target"),
        "avoid_bad_rr": sum(1 for row in rows if row.get("action") == "avoid_bad_rr"),
        "watch_bad_rr": sum(1 for row in rows if row.get("action") == "watch_bad_rr"),
        "watch_ml_rejected": sum(1 for row in rows if row.get("action") == "watch_ml_rejected"),
        "avg_probability_pct": _round(
            sum(float(row.get("target_probability_pct") or 0) for row in rows) / len(rows),
            1,
        ) if rows else None,
    }

    def _diagnostic_reason(row: dict[str, Any]) -> str:
        action_value = row.get("action")
        sizing = row.get("position_sizing") or {}

        if action_value == "avoid_downside_signal":
            return "Исходный сигнал является downside/risk-сценарием, покупка запрещена."
        if action_value == "avoid_bad_target":
            return "Целевая цена не выше текущей цены — long-вход запрещён."
        if action_value == "avoid_bad_rr":
            return "Risk/reward ниже минимального порога."
        if action_value == "avoid_ml_veto":
            return "ML-модель оценила вероятность цели ниже 15%."
        if action_value == "avoid_ml_filter":
            return "ML-корректировка заметно снизила итоговую вероятность."
        if action_value == "avoid_risk":
            return "Риск сценария выше допустимого для текущей вероятности."
        if action_value == "avoid":
            return "Итоговая вероятность ниже минимального потребительского порога."
        if action_value == "watch_ml_confirmed":
            return "ML подтверждает сценарий, но итоговой вероятности пока мало для покупки."
        if action_value == "watch_bad_rr":
            return "Вероятность приемлемая, но risk/reward ниже 1.2."
        if action_value == "watch_ml_rejected":
            return "Rule-сигнал есть, но ML не подтверждает покупку."
        if action_value == "watch":
            return "Нейтральный сигнал: наблюдение без входа."

        return str(row.get("decision_reason") or "Причина не классифицирована.")

    def _next_fix_hint(row: dict[str, Any]) -> str:
        action_value = row.get("action")
        sizing = row.get("position_sizing") or {}

        if action_value == "avoid_downside_signal":
            return "Не чинить как long: это downside-сценарий, его нужно показывать как риск/не покупать."
        if action_value == "avoid_bad_target":
            return "Проверить target generation: цель должна быть выше текущей цены для long-сигнала."
        if action_value == "avoid_bad_rr":
            return "Улучшить цель или подтянуть стоп: текущий RR недостаточен."
        if action_value == "avoid_ml_veto":
            return "Не усиливать вручную: ML явно против сценария."
        if action_value in {"watch_ml_confirmed", "watch"}:
            return "Ждать роста probability/reliability или улучшения RR."
        if action_value == "avoid":
            return "Недостаточно сильный общий сигнал."
        if sizing.get("allowed") is False:
            return "Позиция запрещена risk layer."

        return "Дополнительных действий не требуется."

    rejection_actions = {
        "avoid",
        "avoid_downside_signal",
        "avoid_bad_target",
        "avoid_bad_rr",
        "avoid_ml_filter",
        "avoid_ml_veto",
        "avoid_risk",
        "watch_bad_rr",
        "watch_ml_rejected",
    }

    rejection_reasons: dict[str, int] = {}

    for row in rows:
        action_value = row.get("action")

        if action_value in rejection_actions:
            rejection_reasons[action_value] = rejection_reasons.get(action_value, 0) + 1

    near_misses = []

    for row in rows:
        action_value = row.get("action")
        probability_value = _to_float(row.get("target_probability_pct")) or 0
        ml_value = _to_float(row.get("ml_probability_pct"))
        sizing = row.get("position_sizing") or {}

        if action_value in {"buy", "consider_buy"}:
            continue

        is_near = (
            probability_value >= 40
            or action_value in {"watch", "watch_ml_confirmed", "avoid_bad_rr", "avoid_bad_target"}
            or (ml_value is not None and ml_value >= 35)
        )

        if not is_near:
            continue

        near_misses.append(
            {
                "ticker": row.get("ticker"),
                "name": row.get("name"),
                "action": action_value,
                "recommendation": row.get("recommendation"),
                "decision": row.get("decision"),
                "probability_pct": row.get("target_probability_pct"),
                "rule_probability_pct": row.get("rule_probability_pct"),
                "ml_probability_pct": row.get("ml_probability_pct"),
                "ml_weight": row.get("ml_weight"),
                "ml_regime_multiplier": row.get("ml_regime_multiplier"),
                "news_adjustment_pct": row.get("news_adjustment_pct"),
                "news_effect": row.get("news_effect"),
                "ticker_news_adjustment_pct": row.get("ticker_news_adjustment_pct"),
                "global_event_adjustment_pct": row.get("global_event_adjustment_pct"),
                "global_event_tags": row.get("global_event_tags"),
                "macro_regime_flags": row.get("macro_regime_flags"),
                "global_event_reason": row.get("global_event_reason"),
                "news_relevance_score": row.get("news_relevance_score"),
                "news_source_reliability_score": row.get("news_source_reliability_score"),
                "news_event_scope": row.get("news_event_scope"),
                "news_sentiment": (row.get("news_assessment") or {}).get("sentiment"),
                "news_sentiment_score": (row.get("news_assessment") or {}).get("sentiment_score"),
                "news_summary": (row.get("news_assessment") or {}).get("summary"),
                "source_signal_action": row.get("source_signal_action"),
                "source_signal_type": row.get("source_signal_type"),
                "source_target_price": row.get("source_target_price"),
                "scenario_direction": row.get("scenario_direction"),
                "scenario_reason": row.get("scenario_reason"),
                "target_price": row.get("target_price"),
                "target_distance_pct": sizing.get("target_distance_pct"),
                "stop_distance_pct": sizing.get("stop_distance_pct"),
                "risk_reward_ratio": row.get("risk_reward_ratio"),
                "reliability_level": row.get("reliability_level"),
                "reliability_score": row.get("reliability_score"),
                "risk_level": row.get("risk_level"),
                "blocked_reason": _diagnostic_reason(row),
                "next_fix_hint": _next_fix_hint(row),
            }
        )

    near_misses.sort(
        key=lambda item: (
            float(item.get("probability_pct") or 0),
            float(item.get("ml_probability_pct") or 0),
        ),
        reverse=True,
    )

    diagnostics = {
        "rejection_reasons": rejection_reasons,
        "near_misses": near_misses[:15],
        "near_misses_count": len(near_misses),
        "interpretation": [
            "avoid_bad_target означает, что цель для long-сценария не выше текущей цены.",
            "avoid_bad_rr означает, что цель есть, но risk/reward слишком слабый.",
            "avoid_ml_veto означает, что ML явно против сценария.",
            "watch_ml_confirmed означает, что ML подтверждает сценарий, но итоговой вероятности пока недостаточно.",
        ],
    }

    return {
        "ok": True,
        "mode": "consumer",
        "scenario": scenario_filter,
        "news_filter": news_filter,
        "summary": summary,
        "diagnostics": diagnostics,
        "rows": rows,
        "notes": [
            "Страница не показывает выбор модели: используется единый потребительский прогноз.",
            "Вероятность — это оценка достижения указанной цели в заданном горизонте, а не гарантия результата.",
        ],
    }

# --- Ticker alias resolver wrapper ---
from app.services.ticker_aliases import apply_alias_metadata, resolve_ticker_alias

_build_consumer_signal_for_ticker_without_alias = build_consumer_signal_for_ticker


def build_consumer_signal_for_ticker(
    db: Session,
    ticker: str,
    candles_limit: int = 240,
) -> dict[str, Any]:
    resolution = resolve_ticker_alias(ticker)
    result = _build_consumer_signal_for_ticker_without_alias(
        db=db,
        ticker=resolution["resolved_ticker"],
        candles_limit=candles_limit,
    )

    if isinstance(result, dict):
        apply_alias_metadata(result, resolution)

    return result


_ALIAS_AWARE_CONSUMER_SIGNAL_WRAPPER = True
