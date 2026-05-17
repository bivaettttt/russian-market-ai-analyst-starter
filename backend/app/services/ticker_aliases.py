from __future__ import annotations

from typing import Any


TICKER_ALIASES: dict[str, dict[str, str]] = {
    "YNDX": {
        "resolved_ticker": "YDEX",
        "reason": "Старый тикер Яндекса. В локальном справочнике найден актуальный тикер МКПАО ЯНДЕКС.",
    },
    "PAZL": {
        "resolved_ticker": "PAZA",
        "reason": "Найден похожий актуальный тикер в локальном справочнике MOEX.",
    },
}


def normalize_ticker(ticker: str | None) -> str:
    return str(ticker or "").upper().strip()


def resolve_ticker_alias(ticker: str | None) -> dict[str, Any]:
    requested_ticker = normalize_ticker(ticker)
    alias = TICKER_ALIASES.get(requested_ticker)

    if not alias:
        return {
            "requested_ticker": requested_ticker,
            "resolved_ticker": requested_ticker,
            "alias_used": False,
            "alias_reason": None,
        }

    resolved_ticker = normalize_ticker(alias.get("resolved_ticker"))

    return {
        "requested_ticker": requested_ticker,
        "resolved_ticker": resolved_ticker,
        "alias_used": resolved_ticker != requested_ticker,
        "alias_reason": alias.get("reason"),
    }


def apply_alias_metadata(payload: dict[str, Any], resolution: dict[str, Any]) -> dict[str, Any]:
    payload["requested_ticker"] = resolution.get("requested_ticker")
    payload["resolved_ticker"] = resolution.get("resolved_ticker")
    payload["alias_used"] = bool(resolution.get("alias_used"))
    payload["alias_reason"] = resolution.get("alias_reason")

    alias_payload = {
        "requested_ticker": resolution.get("requested_ticker"),
        "resolved_ticker": resolution.get("resolved_ticker"),
        "used": bool(resolution.get("alias_used")),
        "reason": resolution.get("alias_reason"),
    }

    payload["alias"] = alias_payload

    forecast = payload.get("forecast")
    if isinstance(forecast, dict):
        forecast["requested_ticker"] = resolution.get("requested_ticker")
        forecast["resolved_ticker"] = resolution.get("resolved_ticker")
        forecast["alias_used"] = bool(resolution.get("alias_used"))
        forecast["alias_reason"] = resolution.get("alias_reason")
        forecast["alias"] = alias_payload

    instrument = payload.get("instrument")
    if isinstance(instrument, dict):
        instrument["requested_ticker"] = resolution.get("requested_ticker")
        instrument["resolved_ticker"] = resolution.get("resolved_ticker")
        instrument["alias_used"] = bool(resolution.get("alias_used"))

    return payload
