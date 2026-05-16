from __future__ import annotations

from statistics import mean
from typing import Any

from sqlalchemy.orm import Session

from app.services.signals_data import list_market_signals


DEFAULT_MODEL_VERSIONS = [
    "tech_v1_sma_momentum",
    "tech_v2_rsi_atr",
    "tech_v3_v1_atr_risk",
    "tech_v4_quality_rr",
]


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def _split_model_versions(model_versions: str | None) -> list[str]:
    if not model_versions:
        return DEFAULT_MODEL_VERSIONS

    result = [
        item.strip()
        for item in model_versions.split(",")
        if item.strip()
    ]

    return result or DEFAULT_MODEL_VERSIONS


def _signal_text(signal: dict[str, Any]) -> str:
    parts: list[str] = []

    for key in ("label", "summary", "fallback_error"):
        value = signal.get(key)
        if value:
            parts.append(str(value))

    for reason in signal.get("reasons") or []:
        parts.append(str(reason))

    return " ".join(parts).lower()


def _is_quality_blocked(signal: dict[str, Any]) -> bool:
    text = _signal_text(signal)
    return (
        "заблок" in text
        or "quality-фильтр" in text
        or "quality-filter" in text
        or "buy переведён" in text
    )


def _model_quality_summary(
    model_version: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    rows = data.get("rows") or []
    total = len(rows)

    actions: dict[str, int] = {}
    confidence_values: list[float] = []
    quality_values: list[float] = []
    rr_values: list[float] = []

    blocked_buy_count = 0
    buy_like_count = 0
    hold_count = 0
    risk_count = 0
    no_data_count = 0

    examples: list[dict[str, Any]] = []

    for row in rows:
        signal = row.get("signal") or {}
        action = str(signal.get("action") or "unknown")

        actions[action] = actions.get(action, 0) + 1

        if action in {"buy_watch", "watch_buy"}:
            buy_like_count += 1
        elif action == "hold_watch":
            hold_count += 1
        elif action == "risk_sell_watch":
            risk_count += 1
        elif action in {"no_data", "no_price"}:
            no_data_count += 1

        confidence = _to_float(signal.get("confidence_pct"))
        if confidence is not None:
            confidence_values.append(confidence)

        quality_score = _to_float(signal.get("quality_score"))
        if quality_score is not None:
            quality_values.append(quality_score)

        rr = _to_float(signal.get("risk_reward_ratio"))
        if rr is not None:
            rr_values.append(rr)

        if _is_quality_blocked(signal):
            blocked_buy_count += 1

        if len(examples) < 8:
            examples.append(
                {
                    "ticker": row.get("ticker"),
                    "action": action,
                    "label": signal.get("label"),
                    "confidence_pct": confidence,
                    "quality_score": quality_score,
                    "risk_reward_ratio": rr,
                    "summary": signal.get("summary"),
                    "ticker_url": row.get("ticker_url"),
                }
            )

    rr_coverage_pct = round(len(rr_values) / total * 100, 2) if total else 0.0

    return {
        "model_version": model_version,
        "total": total,
        "actions": actions,
        "buy_like_count": buy_like_count,
        "hold_count": hold_count,
        "risk_count": risk_count,
        "no_data_count": no_data_count,
        "blocked_buy_count": blocked_buy_count,
        "blocked_buy_pct": round(blocked_buy_count / total * 100, 2) if total else 0.0,
        "avg_confidence_pct": _round(mean(confidence_values), 2) if confidence_values else None,
        "avg_quality_score": _round(mean(quality_values), 2) if quality_values else None,
        "risk_reward_count": len(rr_values),
        "risk_reward_coverage_pct": rr_coverage_pct,
        "avg_risk_reward_ratio": _round(mean(rr_values), 2) if rr_values else None,
        "max_risk_reward_ratio": _round(max(rr_values), 2) if rr_values else None,
        "min_risk_reward_ratio": _round(min(rr_values), 2) if rr_values else None,
        "examples": examples,
    }


def build_signal_model_quality_report(
    db: Session,
    model_versions: str | None = None,
    limit: int = 100,
    candles_limit: int = 120,
    action: str | None = None,
) -> dict[str, Any]:
    versions = _split_model_versions(model_versions)

    model_reports: list[dict[str, Any]] = []

    for version in versions:
        data = list_market_signals(
            db=db,
            limit=limit,
            candles_limit=candles_limit,
            action=action,
            model_version=version,
        )

        model_reports.append(
            _model_quality_summary(
                model_version=version,
                data=data,
            )
        )

    best_by_rr = max(
        [item for item in model_reports if item.get("avg_risk_reward_ratio") is not None],
        key=lambda item: item.get("avg_risk_reward_ratio") or 0,
        default=None,
    )

    best_by_confidence = max(
        [item for item in model_reports if item.get("avg_confidence_pct") is not None],
        key=lambda item: item.get("avg_confidence_pct") or 0,
        default=None,
    )

    strictest_by_blocked = max(
        model_reports,
        key=lambda item: item.get("blocked_buy_count") or 0,
        default=None,
    )

    return {
        "ok": True,
        "model_versions": versions,
        "limit": limit,
        "candles_limit": candles_limit,
        "action": action,
        "models": model_reports,
        "best_by_avg_risk_reward": best_by_rr,
        "best_by_avg_confidence": best_by_confidence,
        "strictest_by_blocked_buy_count": strictest_by_blocked,
        "notes": [
            "Quality report использует текущие live-сигналы, а не исторический backtest.",
            "risk_reward_ratio доступен только для моделей/сигналов, где есть entry/target/stop.",
            "blocked_buy_count полезен прежде всего для tech_v4_quality_rr.",
        ],
    }
