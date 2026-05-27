from __future__ import annotations

import json
import re
from typing import Any

from app.services.consumer_signals import _round


EVENT_FAMILIES = {
    "rates",
    "inflation",
    "sanctions",
    "geopolitics",
    "oil_gas",
    "commodities",
    "fx",
    "dividend",
    "earnings",
    "corporate_action",
    "macro",
    "sector_news",
    "ticker_news",
    "market_structure",
    "unknown",
}

EXPORTER_SECTORS = {"oil_gas", "metals", "mining", "exporters", "нефтегаз", "металлурги", "экспортёры"}
KNOWN_MARKET_TICKERS = {
    "AFLT",
    "ETLN",
    "GAZP",
    "GMKN",
    "IMOEX",
    "LKOH",
    "LSRG",
    "MOEX",
    "NVTK",
    "PIKK",
    "PLZL",
    "ROSN",
    "RUAL",
    "SBER",
    "SMLT",
    "SNGS",
    "SPBE",
    "TATN",
    "VTBR",
}


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return " ".join(_as_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(f"{key} {_as_text(item)}" for key, item in value.items())
    return str(value)


def _event_text(event: dict[str, Any]) -> str:
    raw = event.get("raw_analysis")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            pass
    parts = [
        event.get("title"),
        event.get("text"),
        event.get("summary"),
        event.get("reasoning"),
        event.get("category"),
        event.get("event_family"),
        event.get("direction"),
        event.get("event_type"),
        event.get("impact"),
        event.get("tags"),
        event.get("affected_assets"),
        event.get("affected_sectors"),
        raw,
    ]
    return _as_text(parts).lower().replace("ё", "е")


def _has_any(text: str, words: list[str]) -> bool:
    return any(word.lower().replace("ё", "е") in text for word in words)


def _unique(items: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item or "").strip()
        if not text:
            continue
        key = text.lower()
        if key not in seen:
            seen.add(key)
            result.append(text)
    return result


def _ticker_mentions(text: str) -> list[str]:
    candidates = re.findall(r"\b[A-Z]{3,6}\b", text.upper())
    ignored = {"RUB", "USD", "EUR", "OIL", "GAS", "OFZ", "РФ", "ЦБ"}
    return _unique([item for item in candidates if item not in ignored and item in KNOWN_MARKET_TICKERS])


def normalize_event_tags(event: dict[str, Any]) -> list[str]:
    text = _event_text(event)
    tags: list[str] = []
    raw_tags = event.get("tags")
    if isinstance(raw_tags, list):
        tags.extend(str(item).lower().replace("ё", "е") for item in raw_tags)

    patterns = {
        "rate_cut": ["снизил ключевую ставку", "снижение ключевой ставки", "rate cut", "easing", "смягч"],
        "rate_hike": ["повысил ключевую ставку", "повышение ключевой ставки", "rate hike", "ужесточ"],
        "sanctions_relief": ["снятие санкций", "смягчение санкций", "sanctions relief", "исключили из санкционного списка"],
        "new_sanctions": ["новые санкции", "расширение санкций", "sdn", "экспортный контроль", "new sanctions"],
        "geopolitical_escalation": ["эскалац", "военная операция", "конфликт", "удар", "ракета", "risk off", "геополит"],
        "geopolitical_deescalation": ["деэскалац", "мирные переговоры", "перемирие", "deescalation"],
        "oil_up": ["нефть выросла", "рост нефти", "oil price up", "brent вырос", "supply shock", "ормуз"],
        "oil_down": ["нефть снизилась", "падение нефти", "oil price down", "brent упал"],
        "rub_weakness": ["ослабление рубля", "рубль ослаб", "rub weakness", "доллар вырос", "юань вырос"],
        "rub_strength": ["укрепление рубля", "рубль укреп", "rub strength", "доллар снизился"],
        "dividend_positive": ["дивиденд", "дивиденды", "рекомендовал дивиденд", "утвердил дивиденд"],
        "dividend_negative": ["отмена дивиденд", "дивиденды отмен", "дивидендная отсечка", "сократил дивиденд"],
        "earnings_positive": ["прибыль вырос", "выручка вырос", "сильные результаты", "strong earnings", "profit growth"],
        "earnings_negative": ["убыток", "прибыль сниз", "слабые результаты", "weak earnings", "loss"],
        "buyback": ["buyback", "обратный выкуп", "байбэк"],
        "dilution": ["spo", "допэмис", "размещение акций", "dilution"],
        "macro": ["инфляц", "ввп", "промпроизвод", "pmi", "macro"],
        "sector_news": ["сектор", "ипотек", "строител", "транспорт", "потребительский спрос"],
    }
    for tag, words in patterns.items():
        if _has_any(text, words):
            tags.append(tag)
    event_type = str(event.get("event_type") or event.get("category") or "").lower().replace("ё", "е")
    if event_type:
        tags.append(event_type)
    return _unique(tags)


def classify_event_family(event: dict[str, Any]) -> dict[str, Any]:
    tags = normalize_event_tags(event)
    text = _event_text(event)
    explicit_family = str(event.get("event_family") or "").lower().strip()
    explicit_direction = str(event.get("direction") or "").lower().strip()
    family = explicit_family if explicit_family in EVENT_FAMILIES else "unknown"
    direction = explicit_direction if explicit_direction in {"positive", "negative", "mixed", "neutral", "unknown"} else "unknown"
    scope = str(event.get("impact_scope") or "unknown").lower().strip() or "unknown"
    sectors: list[str] = _list_field(event, "affected_sectors")
    asset_types: list[str] = _list_field(event, "affected_asset_types")
    tickers = _ticker_mentions(text) + _list_field(event, "affected_tickers") + _list_field(event, "affected_assets")
    score = int(float(event.get("score") or 0)) if str(event.get("score") or "").strip() else 0
    confidence = str(event.get("confidence") or "low").lower()
    reason = str(event.get("reason") or "Event family is unknown or too ambiguous.")

    if family != "unknown":
        if direction == "unknown":
            direction = _direction_from_impact(event)
        if score == 0:
            score = 35 if direction == "positive" else -35 if direction == "negative" else 10
        return {
            "event_family": family,
            "direction": direction,
            "impact_scope": scope,
            "affected_sectors": _unique(sectors),
            "affected_asset_types": _unique(asset_types),
            "affected_tickers": _unique(tickers),
            "score": int(max(-100, min(100, score))),
            "confidence": confidence if confidence in {"low", "medium", "high"} else "low",
            "tags": tags,
            "reason": reason,
        }

    if any(tag in tags for tag in ["rate_cut", "rate_hike", "rates", "bonds"]):
        family = "rates"
        direction = "positive" if "rate_cut" in tags else "negative" if "rate_hike" in tags else "mixed"
        scope = "market"
        sectors = ["banks", "developers", "bonds", "rate_sensitive"]
        asset_types = ["stock", "bond", "ofz"]
        score = 55 if direction == "positive" else -55 if direction == "negative" else 15
        confidence = "high" if direction != "mixed" else "medium"
        reason = "Rates event affects discount rates, OFZ and rate-sensitive equities."
    elif any(tag in tags for tag in ["sanctions_relief", "new_sanctions", "sanctions"]):
        family = "sanctions"
        direction = "positive" if "sanctions_relief" in tags else "negative" if "new_sanctions" in tags else "mixed"
        scope = "market"
        sectors = ["banks", "exporters", "market"]
        asset_types = ["stock", "currency"]
        score = 65 if direction == "positive" else -70 if direction == "negative" else -20
        confidence = "high"
        reason = "Sanctions change Russia risk premium and can affect banks, exporters and broad market."
    elif any(tag in tags for tag in ["geopolitical_escalation", "geopolitical_deescalation", "geopolitical", "geopolitics"]):
        family = "geopolitics"
        direction = "positive" if "geopolitical_deescalation" in tags else "negative" if "geopolitical_escalation" in tags else "mixed"
        scope = "market"
        sectors = ["market", "oil_gas", "transport", "gold"]
        asset_types = ["stock", "currency", "commodity"]
        score = 55 if direction == "positive" else -65 if direction == "negative" else -20
        confidence = "medium"
        reason = "Geopolitical events usually drive risk premium and risk-off/risk-on behavior."
    elif any(tag in tags for tag in ["oil_up", "oil_down", "commodities", "oil_gas"]):
        family = "oil_gas"
        direction = "positive" if "oil_up" in tags else "negative" if "oil_down" in tags else "mixed"
        scope = "sector"
        sectors = ["oil_gas", "exporters", "transport"]
        asset_types = ["stock", "commodity"]
        score = 50 if direction == "positive" else -50 if direction == "negative" else 10
        confidence = "medium"
        reason = "Oil/gas event primarily affects exporters and energy sector margins."
    elif any(tag in tags for tag in ["rub_weakness", "rub_strength", "fx"]):
        family = "fx"
        direction = "positive" if "rub_weakness" in tags else "negative" if "rub_strength" in tags else "mixed"
        scope = "sector"
        sectors = ["exporters", "oil_gas", "metals", "importers", "consumer"]
        asset_types = ["stock", "currency"]
        score = 45 if direction == "positive" else -35 if direction == "negative" else 10
        confidence = "medium"
        reason = "RUB move is positive for exporters on weakness and mixed/negative for import-heavy sectors."
    elif any(tag in tags for tag in ["dividend_positive", "dividend_negative", "dividends", "dividend"]):
        family = "dividend"
        direction = "negative" if "dividend_negative" in tags else "positive"
        scope = "ticker" if tickers else "sector"
        sectors = ["dividend_stocks"]
        asset_types = ["stock"]
        score = 55 if direction == "positive" else -60
        confidence = "medium"
        reason = "Dividend announcement/cut is a direct ticker or dividend-factor catalyst."
    elif any(tag in tags for tag in ["earnings_positive", "earnings_negative", "earnings"]):
        family = "earnings"
        direction = "positive" if "earnings_positive" in tags else "negative" if "earnings_negative" in tags else "mixed"
        scope = "ticker" if tickers else "sector"
        asset_types = ["stock"]
        score = 55 if direction == "positive" else -55 if direction == "negative" else 10
        confidence = "medium"
        reason = "Earnings event affects expected cash flows."
    elif any(tag in tags for tag in ["buyback", "dilution", "corporate_action"]):
        family = "corporate_action"
        direction = "positive" if "buyback" in tags else "negative" if "dilution" in tags else "mixed"
        scope = "ticker" if tickers else "sector"
        asset_types = ["stock"]
        score = 50 if direction == "positive" else -50 if direction == "negative" else 10
        confidence = "medium"
        reason = "Corporate action changes capital structure or shareholder return."
    elif "macro" in tags:
        family = "macro"
        direction = "mixed"
        scope = "market"
        asset_types = ["stock", "bond", "currency"]
        score = 10
        confidence = "low"
        reason = "Macro event is broad but direction is not reliably inferable from keywords."
    elif "sector_news" in tags:
        family = "sector_news"
        direction = "mixed"
        scope = "sector"
        asset_types = ["stock"]
        score = 10
        confidence = "low"
        reason = "Sector event requires sector-specific interpretation."
    elif tickers:
        family = "ticker_news"
        direction = _direction_from_impact(event)
        scope = "ticker"
        asset_types = ["stock"]
        score = 25 if direction == "positive" else -25 if direction == "negative" else 5
        confidence = "low"
        reason = "Ticker mention detected, but catalyst family is weakly classified."

    return {
        "event_family": family if family in EVENT_FAMILIES else "unknown",
        "direction": direction,
        "impact_scope": scope,
        "affected_sectors": _unique(sectors),
        "affected_asset_types": _unique(asset_types),
        "affected_tickers": _unique(tickers),
        "score": int(max(-100, min(100, score))),
        "confidence": confidence,
        "tags": tags,
        "reason": reason,
    }


def _direction_from_impact(event: dict[str, Any]) -> str:
    impact = str(event.get("impact") or "").lower()
    if "positive" in impact or "позит" in impact:
        return "positive"
    if "negative" in impact or "негат" in impact:
        return "negative"
    if "mixed" in impact or "смеш" in impact:
        return "mixed"
    if "neutral" in impact or "нейтр" in impact:
        return "neutral"
    return "unknown"


def _list_field(event: dict[str, Any], key: str) -> list[str]:
    value = event.get(key)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except Exception:
            return [item.strip() for item in re.split(r"[,;]", value) if item.strip()]
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def map_event_to_market_impact(
    event: dict[str, Any],
    *,
    instrument: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mapped = classify_event_family(event)
    instrument = instrument or {}
    sector = str(instrument.get("sector") or "").lower().replace("ё", "е")
    ticker = str(instrument.get("ticker") or instrument.get("secid") or "").upper()
    asset_type = str(instrument.get("asset_type") or "").lower()
    direction = mapped["direction"]
    score = int(mapped["score"])
    reason = mapped["reason"]

    if mapped["event_family"] == "rates" and asset_type in {"bond", "ofz"}:
        score = abs(score) if direction == "positive" else -abs(score)
    if mapped["event_family"] == "fx" and sector:
        if sector in EXPORTER_SECTORS or any(token in sector for token in ["нефт", "металл", "экспорт"]):
            score = abs(score) if direction == "positive" else -abs(score)
        elif any(token in sector for token in ["consumer", "retail", "air", "transport", "импорт", "авиа", "ритейл"]):
            score = -abs(score) if direction == "positive" else abs(score)
            direction = "negative" if mapped["direction"] == "positive" else "positive"
            reason = "FX event impact is reversed for import-heavy or transport sectors."
    if ticker and ticker in {item.upper() for item in mapped.get("affected_tickers") or []}:
        mapped["impact_scope"] = "ticker"
        mapped["confidence"] = "high" if mapped["confidence"] == "medium" else mapped["confidence"]

    mapped["score"] = _round(max(-100.0, min(100.0, float(score))), 2) or 0.0
    mapped["direction"] = direction
    mapped["reason"] = reason
    return mapped
