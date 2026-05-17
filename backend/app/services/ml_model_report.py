from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.ml_probability_engine import get_ml_probability_status
from app.services.ml_probability_evaluation import evaluate_ml_probability_model


def _best_threshold(
    threshold_report: list[dict[str, Any]],
    base_rate_pct: float | None,
    min_signals: int = 30,
) -> dict[str, Any] | None:
    base = float(base_rate_pct or 0)

    candidates: list[dict[str, Any]] = []

    for row in threshold_report:
        hit_rate = row.get("hit_rate_pct")
        signals = int(row.get("signals") or 0)

        if hit_rate is None or signals < min_signals:
            continue

        enriched = dict(row)
        enriched["lift_vs_base_pct"] = round(float(hit_rate) - base, 2)
        candidates.append(enriched)

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            float(item.get("lift_vs_base_pct") or -999),
            float(item.get("hit_rate_pct") or -999),
            int(item.get("signals") or 0),
        ),
        reverse=True,
    )

    return candidates[0]


def _usage_recommendation(
    status: dict[str, Any],
    evaluation: dict[str, Any],
    best_threshold: dict[str, Any] | None,
) -> dict[str, Any]:
    if not status.get("trained"):
        return {
            "level": "not_trained",
            "title": "ML-модель не обучена",
            "summary": "Сначала нужно обучить ML probability model.",
            "consumer_usage": "disabled",
            "ml_weight_policy": "rule_only",
        }

    metrics = evaluation.get("metrics") or {}
    test_period = evaluation.get("test_period") or {}
    base_rate = test_period.get("positive_rate_pct")

    auc = metrics.get("calibrated_auc")
    brier = metrics.get("calibrated_brier")

    if not evaluation.get("ok") or best_threshold is None:
        return {
            "level": "weak",
            "title": "ML-модель пока не даёт устойчивого преимущества",
            "summary": "Нет порога с достаточным числом сигналов и положительным lift к base rate.",
            "consumer_usage": "risk_filter_only",
            "ml_weight_policy": "low_weight",
            "base_rate_pct": base_rate,
            "calibrated_auc": auc,
            "calibrated_brier": brier,
        }

    lift = float(best_threshold.get("lift_vs_base_pct") or 0)
    signals = int(best_threshold.get("signals") or 0)
    threshold = best_threshold.get("threshold_pct")

    if lift >= 4 and signals >= 100:
        level = "useful_ranker"
        title = "ML-модель полезна как фильтр и ранжировщик"
        consumer_usage = "confirmation_and_risk_filter"
        ml_weight_policy = "moderate_weight_in_valid_band"
        summary = (
            f"Лучший рабочий порог около {threshold}%, lift к base rate: "
            f"{round(lift, 2)} п.п. Модель можно использовать как подтверждение, "
            "но не как самостоятельный сигнал покупки."
        )
    elif lift > 0:
        level = "limited"
        title = "ML-модель даёт ограниченное преимущество"
        consumer_usage = "risk_filter_only"
        ml_weight_policy = "low_weight"
        summary = (
            f"Лучший lift положительный, но умеренный: {round(lift, 2)} п.п. "
            "Использовать осторожно, в основном как риск-фильтр."
        )
    else:
        level = "weak"
        title = "ML-модель не улучшает отбор сигналов"
        consumer_usage = "risk_filter_only"
        ml_weight_policy = "very_low_weight"
        summary = "На текущем test period ML не показывает положительный lift."

    return {
        "level": level,
        "title": title,
        "summary": summary,
        "consumer_usage": consumer_usage,
        "ml_weight_policy": ml_weight_policy,
        "base_rate_pct": base_rate,
        "best_threshold": best_threshold,
        "calibrated_auc": auc,
        "calibrated_brier": brier,
    }


def build_ml_model_report(
    db: Session,
    *,
    thresholds: list[float] | None = None,
    max_samples: int | None = 12_000,
    min_signals: int = 30,
) -> dict[str, Any]:
    status = get_ml_probability_status()

    if not status.get("trained"):
        recommendation = _usage_recommendation(status=status, evaluation={}, best_threshold=None)
        return {
            "ok": False,
            "trained": False,
            "status": status,
            "recommendation": recommendation,
        }

    evaluation = evaluate_ml_probability_model(
        db=db,
        thresholds=thresholds or [0.25, 0.30, 0.35, 0.40, 0.45, 0.50],
        max_samples=max_samples,
    )

    test_period = evaluation.get("test_period") or {}
    threshold_report = evaluation.get("threshold_report") or []

    best = _best_threshold(
        threshold_report=threshold_report,
        base_rate_pct=test_period.get("positive_rate_pct"),
        min_signals=min_signals,
    )

    recommendation = _usage_recommendation(
        status=status,
        evaluation=evaluation,
        best_threshold=best,
    )

    metadata = status.get("metadata") or {}

    return {
        "ok": True,
        "trained": True,
        "model": {
            "target_pct": metadata.get("target_pct"),
            "stop_pct": metadata.get("stop_pct"),
            "horizon": metadata.get("horizon"),
            "feature_set": metadata.get("feature_set"),
            "feature_count": metadata.get("feature_count"),
            "trained_at": metadata.get("trained_at"),
            "date_range": metadata.get("date_range"),
        },
        "status_metrics": status.get("metrics") or {},
        "evaluation": {
            "test_period": test_period,
            "metrics": evaluation.get("metrics") or {},
            "threshold_report": threshold_report,
            "calibration_report": evaluation.get("calibration_report") or [],
            "feature_importance": evaluation.get("feature_importance") or [],
        },
        "best_threshold": best,
        "recommendation": recommendation,
        "interpretation": [
            "Этот отчёт не является торговой рекомендацией.",
            "best_threshold показывает, где ML исторически лучше base rate.",
            "Если lift положительный, ML можно использовать как фильтр/ранжировщик.",
            "Если lift нестабилен, ML не должен быть самостоятельным buy engine.",
        ],
    }
