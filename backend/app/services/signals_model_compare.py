from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.signals_backtest import run_signals_backtest


DEFAULT_MODEL_VERSIONS = [
    "tech_v1_sma_momentum",
    "tech_v2_rsi_atr",
    "tech_v3_v1_atr_risk",
    "tech_v4_quality_rr",
]


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _score_model(summary: dict[str, Any]) -> float:
    """
    Простая оценка качества модели:
    - важнее всего средний результат стратегии;
    - затем точность;
    - штрафуем за малое число actionable-сигналов.
    """
    avg_strategy = _safe_float(summary.get("avg_strategy_result_pct")) or 0.0
    accuracy = _safe_float(summary.get("accuracy_pct")) or 0.0
    actionable_count = int(summary.get("actionable_count") or 0)

    activity_bonus = min(actionable_count, 30) / 30

    return round(avg_strategy * 2 + accuracy * 0.03 + activity_bonus, 2)


def compare_signal_models(
    db: Session,
    tickers: str,
    model_versions: str | None = None,
    limit: int = 150,
    min_history: int = 60,
    future_limit: int = 20,
    max_points_per_ticker: int = 25,
    action: str | None = None,
) -> dict[str, Any]:
    versions = [
        item.strip()
        for item in (model_versions or ",".join(DEFAULT_MODEL_VERSIONS)).split(",")
        if item.strip()
    ]

    rows: list[dict[str, Any]] = []

    for version in versions:
        result = run_signals_backtest(
            db=db,
            tickers=tickers,
            limit=limit,
            min_history=min_history,
            future_limit=future_limit,
            max_points_per_ticker=max_points_per_ticker,
            action=action,
            model_version=version,
        )

        summary = result.get("summary") or {}

        rows.append(
            {
                "model_version": version,
                "score": _score_model(summary),
                "summary": summary,
                "by_action": result.get("by_action") or [],
                "by_ticker": result.get("by_ticker") or [],
                "params": result.get("params") or {},
            }
        )

    rows.sort(
        key=lambda row: (
            _safe_float((row.get("summary") or {}).get("avg_strategy_result_pct")) or -999,
            _safe_float((row.get("summary") or {}).get("accuracy_pct")) or -999,
            int((row.get("summary") or {}).get("actionable_count") or 0),
        ),
        reverse=True,
    )

    winner = rows[0] if rows else None

    return {
        "params": {
            "tickers": tickers,
            "model_versions": versions,
            "limit": limit,
            "min_history": min_history,
            "future_limit": future_limit,
            "max_points_per_ticker": max_points_per_ticker,
            "action": action,
        },
        "winner": winner,
        "rows": rows,
    }
