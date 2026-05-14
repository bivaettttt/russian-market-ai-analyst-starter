from __future__ import annotations

import json

from typing import Any
from pathlib import Path


PRODUCTION_SIGNAL_MODEL_VERSION = "tech_v1_sma_momentum"

SIGNAL_MODELS: dict[str, dict[str, Any]] = {
    "tech_v1_sma_momentum": {
        "title": "tech_v1_sma_momentum",
        "status": "production",
        "kind": "rule_based",
        "description": (
            "Базовая rule-based модель на SMA20/SMA50, momentum и объёме. "
            "Сейчас основная модель, так как показывает лучший backtest-score."
        ),
    },
    "tech_v2_rsi_atr": {
        "title": "tech_v2_rsi_atr",
        "status": "lab",
        "kind": "rule_based",
        "description": (
            "Экспериментальная rule-based модель с RSI и ATR. "
            "Пока хуже production-модели по backtest."
        ),
    },
    "tech_v3_v1_atr_risk": {
        "title": "tech_v3_v1_atr_risk",
        "status": "lab",
        "kind": "rule_based",
        "description": (
            "Экспериментальная гибридная модель: направление от v1, риск-уровни через ATR. "
            "Пока хуже production-модели по backtest."
        ),
    },
}



SIGNAL_MODEL_STATE_PATH = Path("data/signal_model_state.json")


def _read_signal_model_state() -> dict[str, Any]:
    if not SIGNAL_MODEL_STATE_PATH.exists():
        return {}

    try:
        return json.loads(SIGNAL_MODEL_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_signal_model_state(state: dict[str, Any]) -> None:
    SIGNAL_MODEL_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SIGNAL_MODEL_STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_production_signal_model_version() -> str:
    state = _read_signal_model_state()
    value = str(state.get("production_model") or "").strip()

    if value in SIGNAL_MODELS:
        return value

    return PRODUCTION_SIGNAL_MODEL_VERSION


def set_production_signal_model_version(model_version: str) -> dict[str, Any]:
    normalized = normalize_signal_model_version(model_version)

    _write_signal_model_state({
        "production_model": normalized,
    })

    return get_signal_model_info(normalized)


def normalize_signal_model_version(model_version: str | None) -> str:
    value = (model_version or "").strip()

    if value in SIGNAL_MODELS:
        return value

    return get_production_signal_model_version()


def get_signal_model_info(model_version: str | None = None) -> dict[str, Any]:
    selected = normalize_signal_model_version(model_version)
    production = get_production_signal_model_version()

    info = dict(SIGNAL_MODELS[selected])
    info["model_version"] = selected
    info["is_production"] = selected == production
    return info


def list_signal_models() -> list[dict[str, Any]]:
    production = get_production_signal_model_version()

    return [
        {
            "model_version": model_version,
            **info,
            "is_production": model_version == production,
        }
        for model_version, info in SIGNAL_MODELS.items()
    ]
