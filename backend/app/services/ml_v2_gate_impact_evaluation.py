from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.adaptive_trade_calibration import aggregate_trade_pnl_metrics
from app.services.ml_v2_dataset import DEFAULT_POLICY_ID, build_ml_v2_trade_dataset
from app.services.ml_v2_evaluation import predict_ml_v2_probabilities
from app.services.ml_v2_research_gate import load_ml_v2_research_model


DEFAULT_THRESHOLDS = [0.50, 0.55, 0.60, 0.65, 0.70]
DEFAULT_GATE_MODES = ["diagnostic_only", "soft_downgrade", "hard_gate"]
VALID_GATE_MODES = set(DEFAULT_GATE_MODES)


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


def parse_gate_impact_thresholds(raw: str | None = None) -> list[float]:
    if not raw:
        return list(DEFAULT_THRESHOLDS)
    values: list[float] = []
    for item in raw.split(","):
        number = _to_float(item.strip())
        if number is None:
            continue
        if number > 1:
            number = number / 100.0
        if 0.05 <= number <= 0.95 and number not in values:
            values.append(round(number, 4))
    return values or list(DEFAULT_THRESHOLDS)


def parse_gate_modes(raw: str | None = None) -> list[str]:
    if not raw:
        return list(DEFAULT_GATE_MODES)
    modes: list[str] = []
    for item in raw.split(","):
        mode = item.strip().lower()
        if mode in VALID_GATE_MODES and mode not in modes:
            modes.append(mode)
    return modes or list(DEFAULT_GATE_MODES)


def _pnl_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"outcome": row.get("outcome"), "trade_return_pct": row.get("trade_return_pct")} for row in rows]


def _sum_positive(rows: list[dict[str, Any]]) -> float:
    return sum(max(_to_float(row.get("trade_return_pct")) or 0.0, 0.0) for row in rows)


def _sum_negative(rows: list[dict[str, Any]]) -> float:
    return sum(min(_to_float(row.get("trade_return_pct")) or 0.0, 0.0) for row in rows)


def _metric_delta(selected: dict[str, Any], baseline: dict[str, Any], key: str) -> float | None:
    selected_value = _to_float(selected.get(key))
    baseline_value = _to_float(baseline.get(key))
    if selected_value is None or baseline_value is None:
        return None
    return _round(selected_value - baseline_value, 3)


def score_gate_impact_result(
    *,
    selected_avg_trade_return_pct: float | None,
    selected_profit_factor: float | None,
    avg_trade_return_delta_pct: float | None,
    profit_factor_delta: float | None,
    win_rate_delta_pct: float | None,
    stop_hit_delta_pct: float | None,
    selected_samples: int,
    coverage_pct: float | None,
    avoided_losses: int,
    missed_wins: int,
    min_signals: int,
) -> float:
    avg_delta = _to_float(avg_trade_return_delta_pct) or 0.0
    pf_delta = _to_float(profit_factor_delta) or 0.0
    win_delta = _to_float(win_rate_delta_pct) or 0.0
    stop_delta = _to_float(stop_hit_delta_pct) or 0.0
    selected_pf = _to_float(selected_profit_factor) or 0.0
    selected_avg = _to_float(selected_avg_trade_return_pct) or 0.0
    coverage = _to_float(coverage_pct) or 0.0

    score = 0.0
    score += avg_delta * 25
    score += pf_delta * 30
    score += win_delta * 0.5
    score += max(0.0, -stop_delta) * 0.8
    score += max(0.0, selected_pf - 1.0) * 25
    score += max(0.0, selected_avg) * 20
    score -= missed_wins * 0.03
    score += avoided_losses * 0.03

    if selected_samples < min_signals:
        score -= 40
    if coverage < 5:
        score -= 30
    elif coverage < 10:
        score -= 20
    elif coverage < 20:
        score -= 10

    return _round(_clamp(score, -100.0, 100.0), 2) or 0.0


def classify_gate_impact_quality(
    *,
    selected_samples: int,
    selected_profit_factor: float | None,
    selected_avg_trade_return_pct: float | None,
    score: float,
    coverage_pct: float | None,
    min_signals: int,
) -> str:
    coverage = _to_float(coverage_pct) or 0.0
    selected_pf = _to_float(selected_profit_factor)
    selected_avg = _to_float(selected_avg_trade_return_pct)
    if selected_samples < min_signals or coverage < 5:
        return "unstable"
    if selected_pf is not None and selected_avg is not None and selected_pf >= 1.08 and selected_avg > 0 and score >= 25:
        return "good"
    if selected_pf is not None and selected_avg is not None and selected_pf >= 1.02 and selected_avg >= 0 and score >= 10:
        return "medium"
    return "weak"


def _impact_row(
    *,
    gate_mode: str,
    threshold: float,
    baseline_rows: list[dict[str, Any]],
    selected_rows: list[dict[str, Any]],
    filtered_rows: list[dict[str, Any]],
    baseline_metrics: dict[str, Any],
    min_signals: int,
) -> dict[str, Any]:
    selected_metrics = aggregate_trade_pnl_metrics(_pnl_rows(selected_rows))
    filtered_metrics = aggregate_trade_pnl_metrics(_pnl_rows(filtered_rows))
    baseline_samples = len(baseline_rows)
    selected_samples = len(selected_rows)
    filtered_samples = len(filtered_rows)
    coverage_pct = _round(selected_samples / baseline_samples * 100, 2) if baseline_samples else 0.0
    avoided_losses = sum(1 for row in filtered_rows if (_to_float(row.get("trade_return_pct")) or 0.0) < 0)
    missed_wins = sum(1 for row in filtered_rows if (_to_float(row.get("trade_return_pct")) or 0.0) > 0)
    avg_delta = _metric_delta(selected_metrics, baseline_metrics, "avg_trade_return_pct")
    pf_delta = _metric_delta(selected_metrics, baseline_metrics, "profit_factor")
    win_delta = _metric_delta(selected_metrics, baseline_metrics, "win_rate_pct")
    stop_delta = _metric_delta(selected_metrics, baseline_metrics, "stop_hit_rate_pct")
    score = score_gate_impact_result(
        selected_avg_trade_return_pct=selected_metrics.get("avg_trade_return_pct"),
        selected_profit_factor=selected_metrics.get("profit_factor"),
        avg_trade_return_delta_pct=avg_delta,
        profit_factor_delta=pf_delta,
        win_rate_delta_pct=win_delta,
        stop_hit_delta_pct=stop_delta,
        selected_samples=selected_samples,
        coverage_pct=coverage_pct,
        avoided_losses=avoided_losses,
        missed_wins=missed_wins,
        min_signals=min_signals,
    )
    quality = classify_gate_impact_quality(
        selected_samples=selected_samples,
        selected_profit_factor=selected_metrics.get("profit_factor"),
        selected_avg_trade_return_pct=selected_metrics.get("avg_trade_return_pct"),
        score=score,
        coverage_pct=coverage_pct,
        min_signals=min_signals,
    )
    warnings: list[str] = []
    if selected_samples < min_signals:
        warnings.append(f"selected_samples below min_signals={min_signals}")
    if gate_mode == "soft_downgrade":
        warnings.append("soft_downgrade assumes downgraded trades are not opened.")

    return {
        "rank": None,
        "gate_mode": gate_mode,
        "threshold_pct": _round(threshold * 100, 1),
        "baseline_samples": baseline_samples,
        "selected_samples": selected_samples,
        "filtered_samples": filtered_samples,
        "downgraded_samples": filtered_samples if gate_mode == "soft_downgrade" else None,
        "coverage_pct": coverage_pct,
        "baseline_avg_trade_return_pct": baseline_metrics.get("avg_trade_return_pct"),
        "selected_avg_trade_return_pct": selected_metrics.get("avg_trade_return_pct"),
        "avg_trade_return_delta_pct": avg_delta,
        "baseline_profit_factor": baseline_metrics.get("profit_factor"),
        "selected_profit_factor": selected_metrics.get("profit_factor"),
        "profit_factor_delta": pf_delta,
        "baseline_win_rate_pct": baseline_metrics.get("win_rate_pct"),
        "selected_win_rate_pct": selected_metrics.get("win_rate_pct"),
        "win_rate_delta_pct": win_delta,
        "baseline_stop_hit_rate_pct": baseline_metrics.get("stop_hit_rate_pct"),
        "selected_stop_hit_rate_pct": selected_metrics.get("stop_hit_rate_pct"),
        "stop_hit_delta_pct": stop_delta,
        "baseline_target_hit_rate_pct": baseline_metrics.get("target_hit_rate_pct"),
        "selected_target_hit_rate_pct": selected_metrics.get("target_hit_rate_pct"),
        "avoided_losses": avoided_losses,
        "missed_wins": missed_wins,
        "avoided_loss_return_pct": _round(_sum_negative(filtered_rows), 2),
        "missed_win_return_pct": _round(_sum_positive(filtered_rows), 2),
        "filtered_metrics": filtered_metrics,
        "score": score,
        "quality_label": quality,
        "warnings": warnings,
    }


def _diagnostic_row(
    *,
    threshold: float,
    baseline_rows: list[dict[str, Any]],
    passed_rows: list[dict[str, Any]],
    rejected_rows: list[dict[str, Any]],
    baseline_metrics: dict[str, Any],
    min_signals: int,
) -> dict[str, Any]:
    row = _impact_row(
        gate_mode="diagnostic_only",
        threshold=threshold,
        baseline_rows=baseline_rows,
        selected_rows=passed_rows,
        filtered_rows=rejected_rows,
        baseline_metrics=baseline_metrics,
        min_signals=min_signals,
    )
    passed_metrics = aggregate_trade_pnl_metrics(_pnl_rows(passed_rows))
    rejected_metrics = aggregate_trade_pnl_metrics(_pnl_rows(rejected_rows))
    row.update(
        {
            "passed_samples": len(passed_rows),
            "rejected_samples": len(rejected_rows),
            "all_metrics": baseline_metrics,
            "passed_metrics": passed_metrics,
            "rejected_metrics": rejected_metrics,
            "passed_avg_trade_return_pct": passed_metrics.get("avg_trade_return_pct"),
            "rejected_avg_trade_return_pct": rejected_metrics.get("avg_trade_return_pct"),
            "passed_profit_factor": passed_metrics.get("profit_factor"),
            "rejected_profit_factor": rejected_metrics.get("profit_factor"),
            "passed_stop_hit_rate_pct": passed_metrics.get("stop_hit_rate_pct"),
            "rejected_stop_hit_rate_pct": rejected_metrics.get("stop_hit_rate_pct"),
            "passed_vs_rejected_delta": {
                "avg_trade_return_delta_pct": _metric_delta(passed_metrics, rejected_metrics, "avg_trade_return_pct"),
                "profit_factor_delta": _metric_delta(passed_metrics, rejected_metrics, "profit_factor"),
                "stop_hit_delta_pct": _metric_delta(passed_metrics, rejected_metrics, "stop_hit_rate_pct"),
            },
        }
    )
    return row


def _recommendation(best: dict[str, Any] | None, rows: list[dict[str, Any]], artifact_missing: bool = False) -> str:
    if artifact_missing:
        return "artifact_missing"
    if not best:
        return "reject"
    if (
        best.get("quality_label") == "good"
        and (_to_float(best.get("selected_profit_factor")) or 0.0) >= 1.08
        and (_to_float(best.get("selected_avg_trade_return_pct")) or 0.0) > 0
        and (_to_float(best.get("coverage_pct")) or 0.0) >= 10
    ):
        return "needs_walk_forward"
    diagnostic_good = any(
        row.get("gate_mode") == "diagnostic_only"
        and (_to_float(row.get("passed_avg_trade_return_pct")) or 0.0) > (_to_float(row.get("rejected_avg_trade_return_pct")) or 0.0)
        and (_to_float(row.get("passed_profit_factor")) or 0.0) > (_to_float(row.get("rejected_profit_factor")) or 0.0)
        for row in rows
    )
    if diagnostic_good:
        return "diagnostic_only"
    return "reject"


def build_ml_v2_gate_impact_evaluation(
    db: Session,
    *,
    max_tickers: int = 120,
    max_samples: int = 10000,
    min_history: int = 80,
    horizon: int = 30,
    policy_id: str = DEFAULT_POLICY_ID,
    thresholds: list[float] | None = None,
    gate_modes: list[str] | None = None,
    commission_bps: float = 10.0,
    slippage_bps: float = 5.0,
    min_signals: int = 50,
) -> dict[str, Any]:
    threshold_values = thresholds or list(DEFAULT_THRESHOLDS)
    gate_mode_values = [mode for mode in (gate_modes or list(DEFAULT_GATE_MODES)) if mode in VALID_GATE_MODES]
    if not gate_mode_values:
        gate_mode_values = list(DEFAULT_GATE_MODES)

    limitations = [
        "Research-only evaluation; production consumer decision logic is unchanged.",
        "Artifact-based evaluation can contain training leakage if the artifact was trained on the same period.",
        "Use ML v2 high-confidence validation for leakage-safer walk-forward evidence.",
        "Labels are proxy daily-candle trade outcomes with simplified costs.",
        "This is not investment advice.",
    ]
    loaded = load_ml_v2_research_model()
    if not loaded.get("ok"):
        return {
            "ok": False,
            "mode": "ml_v2_gate_impact_evaluation",
            "error": "ml_v2_artifact_not_available" if loaded.get("status") == "not_available" else "ml_v2_artifact_error",
            "recommendation": "artifact_missing",
            "summary": {
                "samples": 0,
                "tickers_used": 0,
                "artifact_status": loaded.get("status") or "not_available",
                "model_version": None,
                "baseline_metrics": {},
                "thresholds": [_round(value * 100, 1) for value in threshold_values],
                "gate_modes": gate_mode_values,
                "best_mode": None,
                "best_threshold_pct": None,
                "best_score": None,
                "best_quality_label": None,
                "recommendation": "artifact_missing",
                "warnings": [loaded.get("reason") or "ML v2 artifact is not available."],
            },
            "best_results": [],
            "results": [],
            "diagnostic_buckets": [],
            "limitations": limitations,
        }

    dataset = build_ml_v2_trade_dataset(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        min_history=min_history,
        horizon=horizon,
        policy_id=policy_id,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
    )
    warnings = list(dataset.get("warnings") or [])
    warnings.append("Current ML v2 artifact is used for scoring; this may contain training leakage.")
    if not dataset.get("ok"):
        return {
            "ok": False,
            "mode": "ml_v2_gate_impact_evaluation",
            "error": "dataset_unavailable",
            "recommendation": "reject",
            "summary": {
                "samples": 0,
                "tickers_used": 0,
                "artifact_status": "available",
                "model_version": loaded.get("model_version"),
                "baseline_metrics": {},
                "thresholds": [_round(value * 100, 1) for value in threshold_values],
                "gate_modes": gate_mode_values,
                "best_mode": None,
                "best_threshold_pct": None,
                "best_score": None,
                "best_quality_label": None,
                "recommendation": "reject",
                "warnings": warnings + ["Could not build ML v2 trade dataset."],
            },
            "best_results": [],
            "results": [],
            "diagnostic_buckets": [],
            "limitations": limitations,
        }

    X = dataset.get("X") or []
    rows = list(dataset.get("rows") or [])
    feature_names = loaded.get("feature_names") or []
    if X and feature_names and len(X[0]) != len(feature_names):
        warnings.append(f"Feature count mismatch: dataset has {len(X[0])}, artifact expects {len(feature_names)}.")

    probabilities = predict_ml_v2_probabilities(loaded["model"], X)
    for row, probability in zip(rows, probabilities):
        row["ml_v2_probability_pct"] = _round(probability * 100, 2)

    baseline_metrics = aggregate_trade_pnl_metrics(_pnl_rows(rows))
    results: list[dict[str, Any]] = []
    diagnostic_buckets: list[dict[str, Any]] = []

    for threshold in threshold_values:
        normalized_threshold = threshold / 100.0 if threshold > 1 else threshold
        passed_rows = [
            row for row in rows if (_to_float(row.get("ml_v2_probability_pct")) or 0.0) >= normalized_threshold * 100
        ]
        rejected_rows = [
            row for row in rows if (_to_float(row.get("ml_v2_probability_pct")) or 0.0) < normalized_threshold * 100
        ]
        if "diagnostic_only" in gate_mode_values:
            row = _diagnostic_row(
                threshold=normalized_threshold,
                baseline_rows=rows,
                passed_rows=passed_rows,
                rejected_rows=rejected_rows,
                baseline_metrics=baseline_metrics,
                min_signals=min_signals,
            )
            results.append(row)
            diagnostic_buckets.append(row)
        for mode in gate_mode_values:
            if mode == "diagnostic_only":
                continue
            results.append(
                _impact_row(
                    gate_mode=mode,
                    threshold=normalized_threshold,
                    baseline_rows=rows,
                    selected_rows=passed_rows,
                    filtered_rows=rejected_rows,
                    baseline_metrics=baseline_metrics,
                    min_signals=min_signals,
                )
            )

    quality_rank = {"good": 3, "medium": 2, "weak": 1, "unstable": 0}
    mode_rank = {"hard_gate": 3, "soft_downgrade": 2, "diagnostic_only": 1}
    results.sort(
        key=lambda item: (
            quality_rank.get(str(item.get("quality_label") or ""), 0),
            float(item.get("score") or -100),
            mode_rank.get(str(item.get("gate_mode") or ""), 0),
            float(item.get("selected_profit_factor") or 0),
            float(item.get("selected_avg_trade_return_pct") or -999),
            float(item.get("coverage_pct") or 0),
        ),
        reverse=True,
    )
    for index, row in enumerate(results, start=1):
        row["rank"] = index

    best = results[0] if results else None
    recommendation = _recommendation(best, results)
    if recommendation == "needs_walk_forward" and best:
        warnings.append("Artifact-based gate looks promising; confirm with walk-forward or paper trading before production use.")

    summary = {
        "samples": len(rows),
        "tickers_used": len({row.get("ticker") for row in rows if row.get("ticker")}),
        "artifact_status": "available",
        "model_version": loaded.get("model_version"),
        "feature_set": loaded.get("feature_set"),
        "baseline_metrics": baseline_metrics,
        "thresholds": [_round((value / 100 if value > 1 else value) * 100, 1) for value in threshold_values],
        "gate_modes": gate_mode_values,
        "best_mode": best.get("gate_mode") if best else None,
        "best_threshold_pct": best.get("threshold_pct") if best else None,
        "best_score": best.get("score") if best else None,
        "best_quality_label": best.get("quality_label") if best else None,
        "recommendation": recommendation,
        "warnings": warnings,
    }
    return {
        "ok": True,
        "mode": "ml_v2_gate_impact_evaluation",
        "summary": summary,
        "best_results": results[:10],
        "results": results,
        "diagnostic_buckets": diagnostic_buckets,
        "limitations": limitations,
    }
