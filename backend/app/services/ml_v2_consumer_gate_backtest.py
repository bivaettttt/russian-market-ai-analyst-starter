from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.adaptive_trade_calibration import aggregate_trade_pnl_metrics
from app.services.candidate_filter_calibration import _apply_trade_policy
from app.services.consumer_signal_backtest_audit import _build_proxy_samples
from app.services.consumer_signals import ML_V2_LONG_CANDIDATE_ACTIONS, _round, _to_float
from app.services.ml_probability_engine import _brier, _safe_auc
from app.services.ml_v2_dataset import DEFAULT_POLICY_ID, build_ml_v2_feature_row
from app.services.ml_v2_evaluation import predict_ml_v2_probabilities, train_ml_v2_classifier
from app.services.ml_v2_gate_impact_evaluation import (
    DEFAULT_GATE_MODES,
    DEFAULT_THRESHOLDS,
    VALID_GATE_MODES,
    parse_gate_impact_thresholds,
    parse_gate_modes,
)
from app.services.ml_v2_research_gate import load_ml_v2_research_model


ACTIVE_LONG_ACTIONS = set(ML_V2_LONG_CANDIDATE_ACTIONS)


def is_long_candidate_action(action: str | None) -> bool:
    return str(action or "").strip().lower() in ACTIVE_LONG_ACTIONS


def _is_active_trade_action(action: str | None) -> bool:
    return is_long_candidate_action(action)


def apply_ml_v2_gate_to_historical_action(
    *,
    original_action: str,
    ml_v2_probability_pct: float | None,
    threshold_pct: float,
    gate_mode: str,
    ml_v2_status: str = "available",
) -> dict[str, Any]:
    action = str(original_action or "unknown")
    mode = str(gate_mode or "diagnostic_only").strip().lower()
    active_before = _is_active_trade_action(action)

    if ml_v2_status != "available" or ml_v2_probability_pct is None:
        return {
            "final_action": action,
            "action_changed": False,
            "gate_effect": "none_not_available",
            "active_trade": active_before,
            "reason": "ML v2 probability is not available.",
        }

    if mode == "diagnostic_only":
        return {
            "final_action": action,
            "action_changed": False,
            "gate_effect": "diagnostic_only",
            "active_trade": active_before,
            "reason": "Diagnostic mode does not change historical action.",
        }

    probability = _to_float(ml_v2_probability_pct)
    threshold = _to_float(threshold_pct) or 0.0
    passed = probability is not None and probability >= threshold
    if not active_before:
        return {
            "final_action": action,
            "action_changed": False,
            "gate_effect": "not_long_candidate",
            "active_trade": False,
            "reason": "Original action is not a long candidate.",
        }

    if passed:
        return {
            "final_action": action,
            "action_changed": False,
            "gate_effect": "passed_no_change",
            "active_trade": True,
            "reason": "ML v2 probability passed threshold.",
        }

    if mode == "soft_downgrade":
        return {
            "final_action": "watch_ml_v2_rejected",
            "action_changed": True,
            "gate_effect": "soft_downgraded",
            "active_trade": False,
            "reason": "ML v2 probability is below threshold; active trade removed in simulation.",
        }
    if mode == "hard_gate":
        return {
            "final_action": "avoid_ml_v2_rejected",
            "action_changed": True,
            "gate_effect": "hard_rejected",
            "active_trade": False,
            "reason": "ML v2 probability is below threshold; active trade rejected in simulation.",
        }

    return {
        "final_action": action,
        "action_changed": False,
        "gate_effect": "unsupported_mode",
        "active_trade": active_before,
        "reason": f"Unsupported gate mode: {mode}.",
    }


def _pnl_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"outcome": row.get("outcome"), "trade_return_pct": row.get("trade_return_pct")} for row in rows]


def _sum_positive(rows: list[dict[str, Any]]) -> float:
    return sum(max(_to_float(row.get("trade_return_pct")) or 0.0, 0.0) for row in rows)


def _sum_negative(rows: list[dict[str, Any]]) -> float:
    return sum(min(_to_float(row.get("trade_return_pct")) or 0.0, 0.0) for row in rows)


def _metric_delta(left: dict[str, Any], right: dict[str, Any], key: str) -> float | None:
    left_value = _to_float(left.get(key))
    right_value = _to_float(right.get(key))
    if left_value is None or right_value is None:
        return None
    return _round(left_value - right_value, 3)


def score_ml_v2_consumer_gate_backtest_result(
    *,
    selected_avg_trade_return_pct: float | None,
    selected_profit_factor: float | None,
    avg_trade_return_delta_pct: float | None,
    profit_factor_delta: float | None,
    win_rate_delta_pct: float | None,
    stop_hit_delta_pct: float | None,
    selected_active_trades: int,
    coverage_pct: float | None,
    avoided_losses: int,
    missed_wins: int,
    min_signals: int,
) -> float:
    avg_delta = _to_float(avg_trade_return_delta_pct) or 0.0
    pf_delta = _to_float(profit_factor_delta) or 0.0
    selected_pf = _to_float(selected_profit_factor) or 0.0
    selected_avg = _to_float(selected_avg_trade_return_pct) or 0.0
    win_delta = _to_float(win_rate_delta_pct) or 0.0
    stop_delta = _to_float(stop_hit_delta_pct) or 0.0
    coverage = _to_float(coverage_pct) or 0.0

    score = 0.0
    score += avg_delta * 25
    score += pf_delta * 30
    score += max(0.0, selected_pf - 1.0) * 25
    score += max(0.0, selected_avg) * 20
    score += win_delta * 0.5
    score += max(0.0, -stop_delta) * 0.8
    score += avoided_losses * 0.03
    score -= missed_wins * 0.05
    if selected_active_trades < min_signals:
        score -= 40
    if coverage < 5:
        score -= 30
    elif coverage < 10:
        score -= 20
    elif coverage < 20:
        score -= 10
    return _round(max(-100.0, min(100.0, score)), 2) or 0.0


def classify_ml_v2_consumer_gate_backtest_quality(
    *,
    selected_active_trades: int,
    selected_profit_factor: float | None,
    selected_avg_trade_return_pct: float | None,
    score: float,
    coverage_pct: float | None,
    min_signals: int,
) -> str:
    coverage = _to_float(coverage_pct) or 0.0
    selected_pf = _to_float(selected_profit_factor)
    selected_avg = _to_float(selected_avg_trade_return_pct)
    if selected_active_trades < min_signals or coverage < 5:
        return "unstable"
    if selected_pf is not None and selected_avg is not None and selected_pf >= 1.08 and selected_avg > 0 and score >= 25:
        return "good"
    if selected_pf is not None and selected_avg is not None and selected_pf >= 1.02 and selected_avg >= 0 and score >= 10:
        return "medium"
    return "weak"


def _baseline_metrics(active_rows: list[dict[str, Any]], total_rows: int) -> dict[str, Any]:
    metrics = aggregate_trade_pnl_metrics(_pnl_rows(active_rows))
    return {
        "baseline_samples": total_rows,
        "baseline_active_trades": len(active_rows),
        "baseline_avg_trade_return_pct": metrics.get("avg_trade_return_pct"),
        "baseline_profit_factor": metrics.get("profit_factor"),
        "baseline_win_rate_pct": metrics.get("win_rate_pct"),
        "baseline_stop_hit_rate_pct": metrics.get("stop_hit_rate_pct"),
        "baseline_target_hit_rate_pct": metrics.get("target_hit_rate_pct"),
        "baseline_timeout_rate_pct": metrics.get("timeout_rate_pct"),
        "raw": metrics,
    }


def _build_result_row(
    *,
    gate_mode: str,
    threshold_pct: float,
    rows: list[dict[str, Any]],
    baseline_active_rows: list[dict[str, Any]],
    min_signals: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    baseline = aggregate_trade_pnl_metrics(_pnl_rows(baseline_active_rows))
    selected_rows: list[dict[str, Any]] = []
    filtered_rows: list[dict[str, Any]] = []
    changed_examples: list[dict[str, Any]] = []
    changed_to_watch = 0
    changed_to_avoid = 0

    for sample in rows:
        original_action = str(sample.get("baseline_action") or sample.get("action") or "unknown")
        application = apply_ml_v2_gate_to_historical_action(
            original_action=original_action,
            ml_v2_probability_pct=_to_float(sample.get("ml_v2_probability_pct")),
            threshold_pct=threshold_pct,
            gate_mode=gate_mode,
            ml_v2_status=str(sample.get("ml_v2_status") or "available"),
        )
        enriched = {**sample, **application, "original_action": original_action}
        if application["active_trade"]:
            selected_rows.append(enriched)
        elif _is_active_trade_action(original_action):
            filtered_rows.append(enriched)
        if application["action_changed"]:
            final_action = str(application.get("final_action") or "")
            changed_to_watch += 1 if final_action == "watch_ml_v2_rejected" else 0
            changed_to_avoid += 1 if final_action == "avoid_ml_v2_rejected" else 0
            if len(changed_examples) < 25:
                changed_examples.append(
                    {
                        "ticker": sample.get("ticker"),
                        "date": sample.get("date"),
                        "original_action": original_action,
                        "final_action": application.get("final_action"),
                        "ml_v2_probability_pct": sample.get("ml_v2_probability_pct"),
                        "threshold_pct": _round(threshold_pct, 1),
                        "trade_return_pct": sample.get("trade_return_pct"),
                        "outcome": sample.get("outcome"),
                        "reason": application.get("reason"),
                    }
                )

    selected = aggregate_trade_pnl_metrics(_pnl_rows(selected_rows))
    filtered = aggregate_trade_pnl_metrics(_pnl_rows(filtered_rows))
    baseline_active = len(baseline_active_rows)
    selected_active = len(selected_rows)
    filtered_count = len(filtered_rows)
    coverage_pct = _round(selected_active / baseline_active * 100, 2) if baseline_active else 0.0
    avoided_losses = sum(1 for row in filtered_rows if (_to_float(row.get("trade_return_pct")) or 0.0) < 0)
    missed_wins = sum(1 for row in filtered_rows if (_to_float(row.get("trade_return_pct")) or 0.0) > 0)
    avg_delta = _metric_delta(selected, baseline, "avg_trade_return_pct")
    pf_delta = _metric_delta(selected, baseline, "profit_factor")
    win_delta = _metric_delta(selected, baseline, "win_rate_pct")
    stop_delta = _metric_delta(selected, baseline, "stop_hit_rate_pct")
    target_delta = _metric_delta(selected, baseline, "target_hit_rate_pct")
    score = score_ml_v2_consumer_gate_backtest_result(
        selected_avg_trade_return_pct=selected.get("avg_trade_return_pct"),
        selected_profit_factor=selected.get("profit_factor"),
        avg_trade_return_delta_pct=avg_delta,
        profit_factor_delta=pf_delta,
        win_rate_delta_pct=win_delta,
        stop_hit_delta_pct=stop_delta,
        selected_active_trades=selected_active,
        coverage_pct=coverage_pct,
        avoided_losses=avoided_losses,
        missed_wins=missed_wins,
        min_signals=min_signals,
    )
    quality = classify_ml_v2_consumer_gate_backtest_quality(
        selected_active_trades=selected_active,
        selected_profit_factor=selected.get("profit_factor"),
        selected_avg_trade_return_pct=selected.get("avg_trade_return_pct"),
        score=score,
        coverage_pct=coverage_pct,
        min_signals=min_signals,
    )
    warnings: list[str] = []
    if selected_active < min_signals:
        warnings.append(f"selected_active_trades below min_signals={min_signals}")
    if gate_mode == "soft_downgrade":
        warnings.append("soft_downgrade assumes downgraded historical candidates are not opened.")
    row = {
        "rank": None,
        "gate_mode": gate_mode,
        "threshold_pct": _round(threshold_pct, 1),
        "baseline_samples": len(rows),
        "baseline_active_trades": baseline_active,
        "baseline_avg_trade_return_pct": baseline.get("avg_trade_return_pct"),
        "baseline_profit_factor": baseline.get("profit_factor"),
        "baseline_win_rate_pct": baseline.get("win_rate_pct"),
        "baseline_stop_hit_rate_pct": baseline.get("stop_hit_rate_pct"),
        "baseline_target_hit_rate_pct": baseline.get("target_hit_rate_pct"),
        "selected_samples": selected_active,
        "selected_active_trades": selected_active,
        "active_trades": selected_active,
        "filtered_samples": filtered_count,
        "downgraded_samples": filtered_count if gate_mode == "soft_downgrade" else 0,
        "coverage_pct": coverage_pct,
        "selected_avg_trade_return_pct": selected.get("avg_trade_return_pct"),
        "selected_profit_factor": selected.get("profit_factor"),
        "selected_win_rate_pct": selected.get("win_rate_pct"),
        "selected_stop_hit_rate_pct": selected.get("stop_hit_rate_pct"),
        "selected_target_hit_rate_pct": selected.get("target_hit_rate_pct"),
        "selected_timeout_rate_pct": selected.get("timeout_rate_pct"),
        "avg_trade_return_delta_pct": avg_delta,
        "profit_factor_delta": pf_delta,
        "win_rate_delta_pct": win_delta,
        "stop_hit_delta_pct": stop_delta,
        "target_hit_delta_pct": target_delta,
        "avoided_losses": avoided_losses,
        "missed_wins": missed_wins,
        "avoided_loss_return_pct": _round(_sum_negative(filtered_rows), 2),
        "missed_win_return_pct": _round(_sum_positive(filtered_rows), 2),
        "changed_actions": changed_to_watch + changed_to_avoid,
        "changed_to_watch": changed_to_watch,
        "changed_to_avoid": changed_to_avoid,
        "filtered_metrics": filtered,
        "score": score,
        "quality_label": quality,
        "warnings": warnings,
    }
    if gate_mode == "diagnostic_only":
        passed = [
            row
            for row in baseline_active_rows
            if (_to_float(row.get("ml_v2_probability_pct")) is not None and (_to_float(row.get("ml_v2_probability_pct")) or 0.0) >= threshold_pct)
        ]
        rejected = [
            row
            for row in baseline_active_rows
            if (_to_float(row.get("ml_v2_probability_pct")) is not None and (_to_float(row.get("ml_v2_probability_pct")) or 0.0) < threshold_pct)
        ]
        passed_metrics = aggregate_trade_pnl_metrics(_pnl_rows(passed))
        rejected_metrics = aggregate_trade_pnl_metrics(_pnl_rows(rejected))
        row.update(
            {
                "passed_samples": len(passed),
                "rejected_samples": len(rejected),
                "passed_avg_trade_return_pct": passed_metrics.get("avg_trade_return_pct"),
                "rejected_avg_trade_return_pct": rejected_metrics.get("avg_trade_return_pct"),
                "passed_profit_factor": passed_metrics.get("profit_factor"),
                "rejected_profit_factor": rejected_metrics.get("profit_factor"),
                "passed_stop_hit_rate_pct": passed_metrics.get("stop_hit_rate_pct"),
                "rejected_stop_hit_rate_pct": rejected_metrics.get("stop_hit_rate_pct"),
            }
        )
    return row, changed_examples


def _prepare_rows(
    db: Session,
    *,
    max_tickers: int,
    max_samples: int,
    min_history: int,
    horizon: int,
    policy_id: str,
    commission_bps: float,
    slippage_bps: float,
) -> tuple[list[list[float]], list[int], list[dict[str, Any]], list[str], set[str], dict[str, Any]]:
    warnings: list[str] = []
    use_best_policy = policy_id == DEFAULT_POLICY_ID
    if not use_best_policy:
        warnings.append(f"Unsupported policy_id={policy_id}; using fixed 5/3/horizon fallback.")
    base_samples, tickers_used = _build_proxy_samples(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        horizon=max(horizon, 30 if use_best_policy else horizon),
        target_pct=0.05,
        stop_pct=0.03,
        min_history=min_history,
        use_market_regime_filter=False,
        commission_bps=0.0,
        slippage_bps=0.0,
    )
    samples, policy_warnings, policy = _apply_trade_policy(
        base_samples,
        horizon=horizon,
        target_pct=0.05,
        stop_pct=0.03,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        use_best_adaptive_policy=use_best_policy,
    )
    warnings.extend(policy_warnings)

    X: list[list[float]] = []
    y: list[int] = []
    rows: list[dict[str, Any]] = []
    for sample in samples[:max_samples]:
        trade_return = _to_float(sample.get("trade_return_pct"))
        if trade_return is None:
            continue
        action = str(sample.get("baseline_action") or sample.get("action") or "unknown")
        row = {
            **sample,
            "baseline_action": action,
            "baseline_recommendation": sample.get("recommendation"),
            "target_probability_pct": sample.get("probability_pct"),
            "ml_probability_pct": sample.get("proxy_ml_probability_pct"),
            "audit_confidence": sample.get("audit_confidence_level"),
            "trade_return_pct": _round(trade_return, 4),
        }
        X.append(build_ml_v2_feature_row(sample))
        y.append(1 if trade_return > 0 else 0)
        rows.append(row)
    dates = [str(row.get("date") or "") for row in rows]
    return X, y, rows, dates, tickers_used, {"warnings": warnings, "policy": policy}


def _score_leakage_safe(
    *,
    X: list[list[float]],
    y: list[int],
    rows: list[dict[str, Any]],
    dates: list[str],
    folds: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    order = sorted(range(len(X)), key=lambda index: dates[index])
    X_sorted = [X[index] for index in order]
    y_sorted = [y[index] for index in order]
    rows_sorted = [rows[index] for index in order]
    dates_sorted = [dates[index] for index in order]
    scored: list[dict[str, Any]] = []
    fold_results: list[dict[str, Any]] = []
    total = len(X_sorted)
    if total < folds * 20:
        warnings.append("Few samples for requested leakage-safe folds; estimates may be unstable.")

    for fold_index in range(1, folds + 1):
        train_end = int(total * fold_index / (folds + 1))
        test_end = int(total * (fold_index + 1) / (folds + 1))
        if train_end < 20 or test_end <= train_end:
            fold_results.append({"fold": fold_index, "warnings": ["fold skipped: not enough train/test samples"]})
            continue
        X_train, X_test = X_sorted[:train_end], X_sorted[train_end:test_end]
        y_train, y_test = y_sorted[:train_end], y_sorted[train_end:test_end]
        rows_test = rows_sorted[train_end:test_end]
        fold_warnings: list[str] = []
        if len(set(y_train)) < 2 or len(set(y_test)) < 2:
            fold_warnings.append("fold skipped: train or test split has only one class")
            fold_results.append({"fold": fold_index, "warnings": fold_warnings})
            continue
        model, error = train_ml_v2_classifier(X_train, y_train)
        if model is None:
            fold_warnings.append(error or "fold skipped: model training failed")
            fold_results.append({"fold": fold_index, "warnings": fold_warnings})
            continue
        probabilities = predict_ml_v2_probabilities(model, X_test)
        for sample, probability in zip(rows_test, probabilities):
            scored.append({**sample, "ml_v2_probability_pct": _round(probability * 100, 2), "ml_v2_status": "available"})
        fold_results.append(
            {
                "fold": fold_index,
                "train_period": {"first_date": dates_sorted[0] if dates_sorted[:train_end] else None, "last_date": dates_sorted[train_end - 1], "samples": train_end},
                "test_period": {"first_date": dates_sorted[train_end] if dates_sorted[train_end:test_end] else None, "last_date": dates_sorted[test_end - 1], "samples": len(X_test)},
                "train_positive_rate_pct": _round(sum(y_train) / len(y_train) * 100, 2),
                "test_positive_rate_pct": _round(sum(y_test) / len(y_test) * 100, 2),
                "auc": _safe_auc(y_test, probabilities),
                "brier": _brier(y_test, probabilities),
                "warnings": fold_warnings,
            }
        )
    if not scored:
        warnings.append("No leakage-safe fold produced predictions.")
    return scored, fold_results, warnings


def _score_artifact(
    *,
    X: list[list[float]],
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    loaded = load_ml_v2_research_model()
    if not loaded.get("ok"):
        return [], [loaded.get("reason") or "ML v2 artifact is not available."], loaded
    probabilities = predict_ml_v2_probabilities(loaded["model"], X)
    scored = [{**sample, "ml_v2_probability_pct": _round(probability * 100, 2), "ml_v2_status": "available"} for sample, probability in zip(rows, probabilities)]
    return scored, ["Artifact mode can contain training leakage if the artifact saw the evaluated period."], loaded


def _recommendation(best: dict[str, Any] | None, *, leakage_safe: bool, baseline_active: int, min_signals: int) -> str:
    if baseline_active < min_signals:
        return "needs_more_data"
    if not best:
        return "reject"
    quality = str(best.get("quality_label") or "")
    selected_pf = _to_float(best.get("selected_profit_factor")) or 0.0
    selected_avg = _to_float(best.get("selected_avg_trade_return_pct")) or 0.0
    coverage = _to_float(best.get("coverage_pct")) or 0.0
    avg_delta = _to_float(best.get("avg_trade_return_delta_pct")) or 0.0
    pf_delta = _to_float(best.get("profit_factor_delta")) or 0.0
    if quality == "good" and selected_pf >= 1.08 and selected_avg > 0 and coverage >= 10 and leakage_safe:
        return "promising_experimental_gate"
    if selected_avg > 0 and (avg_delta > 0 or pf_delta > 0) and quality in {"good", "medium", "weak", "unstable"}:
        return "research_only"
    return "reject"


def build_ml_v2_consumer_gate_backtest(
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
    use_leakage_safe_predictions: bool = True,
    folds: int = 4,
) -> dict[str, Any]:
    threshold_values = thresholds or list(DEFAULT_THRESHOLDS)
    threshold_pcts = [_round((value / 100.0 if value > 1 else value) * 100, 1) or 0.0 for value in threshold_values]
    gate_mode_values = [mode for mode in (gate_modes or list(DEFAULT_GATE_MODES)) if mode in VALID_GATE_MODES]
    if not gate_mode_values:
        gate_mode_values = list(DEFAULT_GATE_MODES)
    limitations = [
        "Historical consumer actions are proxy reconstructed.",
        "Historical outcomes are proxy labels from daily candles.",
        "Daily candles cannot fully resolve intraday target/stop ordering.",
        "Costs are simplified commission/slippage assumptions.",
        "This does not change production defaults and does not replace ML v1.",
        "Paper trading validation is required before any production use.",
    ]

    X, y, rows, dates, tickers_used, prep = _prepare_rows(
        db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        min_history=min_history,
        horizon=horizon,
        policy_id=policy_id,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
    )
    warnings = list(prep.get("warnings") or [])
    warnings.append("Historical consumer actions are proxy reconstructed.")
    if not rows:
        return {
            "ok": True,
            "mode": "ml_v2_consumer_gate_backtest",
            "summary": {
                "samples": 0,
                "tickers_used": 0,
                "prediction_mode": "leakage_safe_walk_forward" if use_leakage_safe_predictions else "artifact",
                "baseline_metrics": {},
                "thresholds": threshold_pcts,
                "gate_modes": gate_mode_values,
                "recommendation": "needs_more_data",
                "warnings": warnings + ["No historical samples were built."],
            },
            "best_results": [],
            "results": [],
            "folds": [],
            "changed_examples": [],
            "limitations": limitations,
        }

    fold_results: list[dict[str, Any]] = []
    artifact_info: dict[str, Any] = {}
    if use_leakage_safe_predictions:
        scored_rows, fold_results, score_warnings = _score_leakage_safe(X=X, y=y, rows=rows, dates=dates, folds=folds)
        warnings.extend(score_warnings)
        prediction_mode = "leakage_safe_walk_forward"
    else:
        scored_rows, score_warnings, artifact_info = _score_artifact(X=X, rows=rows)
        warnings.extend(score_warnings)
        prediction_mode = "artifact"
        if not scored_rows:
            return {
                "ok": False,
                "mode": "ml_v2_consumer_gate_backtest",
                "error": "artifact_missing" if artifact_info.get("status") == "not_available" else "artifact_error",
                "summary": {
                    "samples": len(rows),
                    "tickers_used": len(tickers_used),
                    "prediction_mode": prediction_mode,
                    "artifact_status": artifact_info.get("status") or "not_available",
                    "baseline_metrics": {},
                    "thresholds": threshold_pcts,
                    "gate_modes": gate_mode_values,
                    "recommendation": "needs_more_data",
                    "warnings": warnings,
                },
                "best_results": [],
                "results": [],
                "folds": [],
                "changed_examples": [],
                "limitations": limitations,
            }

    baseline_active_rows = [row for row in scored_rows if _is_active_trade_action(row.get("baseline_action") or row.get("action"))]
    baseline_summary = _baseline_metrics(baseline_active_rows, len(scored_rows))
    if len(baseline_active_rows) < min_signals:
        warnings.append("Baseline active consumer trades are below min_signals; estimates are unstable.")

    results: list[dict[str, Any]] = []
    changed_examples: list[dict[str, Any]] = []
    for threshold_pct in threshold_pcts:
        for gate_mode in gate_mode_values:
            row, examples = _build_result_row(
                gate_mode=gate_mode,
                threshold_pct=threshold_pct,
                rows=scored_rows,
                baseline_active_rows=baseline_active_rows,
                min_signals=min_signals,
            )
            results.append(row)
            changed_examples.extend(examples)

    quality_rank = {"good": 3, "medium": 2, "weak": 1, "unstable": 0}
    mode_rank = {"hard_gate": 3, "soft_downgrade": 2, "diagnostic_only": 1}
    results.sort(
        key=lambda row: (
            quality_rank.get(str(row.get("quality_label") or ""), 0),
            _to_float(row.get("score")) if _to_float(row.get("score")) is not None else -999,
            mode_rank.get(str(row.get("gate_mode") or ""), 0),
            _to_float(row.get("selected_profit_factor")) if _to_float(row.get("selected_profit_factor")) is not None else -999,
            _to_float(row.get("selected_avg_trade_return_pct")) if _to_float(row.get("selected_avg_trade_return_pct")) is not None else -999,
        ),
        reverse=True,
    )
    for rank, row in enumerate(results, start=1):
        row["rank"] = rank
    best = results[0] if results else None
    recommendation = _recommendation(
        best,
        leakage_safe=use_leakage_safe_predictions,
        baseline_active=len(baseline_active_rows),
        min_signals=min_signals,
    )
    summary = {
        "samples": len(scored_rows),
        "tickers_used": len({row.get("ticker") for row in scored_rows if row.get("ticker")}) or len(tickers_used),
        "prediction_mode": prediction_mode,
        "artifact_status": artifact_info.get("status") if artifact_info else None,
        "baseline_metrics": baseline_summary,
        "thresholds": threshold_pcts,
        "gate_modes": gate_mode_values,
        "best_gate_mode": best.get("gate_mode") if best else None,
        "best_threshold_pct": best.get("threshold_pct") if best else None,
        "best_score": best.get("score") if best else None,
        "best_quality_label": best.get("quality_label") if best else None,
        "recommendation": recommendation,
        "warnings": warnings,
    }
    return {
        "ok": True,
        "mode": "ml_v2_consumer_gate_backtest",
        "summary": summary,
        "best_results": results[:10],
        "results": results,
        "folds": fold_results if use_leakage_safe_predictions else [],
        "changed_examples": changed_examples[:25],
        "limitations": limitations,
    }


parse_ml_v2_consumer_gate_backtest_thresholds = parse_gate_impact_thresholds
parse_ml_v2_consumer_gate_backtest_modes = parse_gate_modes
