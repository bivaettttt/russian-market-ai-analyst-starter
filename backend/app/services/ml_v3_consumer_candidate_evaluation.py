from __future__ import annotations

from statistics import median
from typing import Any

from sqlalchemy.orm import Session

from app.services.adaptive_trade_calibration import aggregate_trade_pnl_metrics
from app.services.consumer_signals import _round, _to_float
from app.services.ml_probability_engine import _brier, _safe_auc
from app.services.ml_v2_evaluation import ml_v2_feature_importance, predict_ml_v2_probabilities, train_ml_v2_classifier
from app.services.ml_v2_gate_impact_evaluation import DEFAULT_GATE_MODES, VALID_GATE_MODES, parse_gate_modes
from app.services.ml_v2_gate_walk_forward import build_gate_walk_forward_ranges
from app.services.ml_v3_consumer_candidate_dataset import (
    DEFAULT_POLICY_ID,
    build_ml_v3_consumer_candidate_dataset,
)


SUPPORTED_LABELS = {"positive_trade_return", "good_trade", "avoid_loss", "target_hit", "avoid_stop"}
EVALUATION_THRESHOLDS = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]
WALK_FORWARD_THRESHOLDS = [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]


def parse_ml_v3_thresholds(raw: str | None = None, *, defaults: list[float] | None = None) -> list[float]:
    if not raw:
        return list(defaults or WALK_FORWARD_THRESHOLDS)
    values: list[float] = []
    for item in raw.split(","):
        value = _to_float(item.strip())
        if value is None:
            continue
        if value > 1:
            value /= 100.0
        if 0.05 <= value <= 0.95 and round(value, 4) not in values:
            values.append(round(value, 4))
    return values or list(defaults or WALK_FORWARD_THRESHOLDS)


def _period(dates: list[str]) -> dict[str, Any]:
    return {"samples": len(dates), "first_date": dates[0] if dates else None, "last_date": dates[-1] if dates else None}


def _rate(count: int, total: int) -> float | None:
    return _round(count / total * 100, 2) if total else None


def _pnl(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return aggregate_trade_pnl_metrics(
        [{"outcome": row.get("outcome"), "trade_return_pct": row.get("trade_return_pct")} for row in rows]
    )


def _metric_delta(left: dict[str, Any], right: dict[str, Any], key: str) -> float | None:
    left_value = _to_float(left.get(key))
    right_value = _to_float(right.get(key))
    if left_value is None or right_value is None:
        return None
    return _round(left_value - right_value, 3)


def _quality(signals: int, profit_factor: float | None, avg_return: float | None, coverage_pct: float | None, min_signals: int = 30) -> str:
    coverage = _to_float(coverage_pct) or 0.0
    pf = _to_float(profit_factor)
    avg = _to_float(avg_return)
    if signals < min_signals or coverage < 5:
        return "unstable"
    if pf is not None and avg is not None and pf >= 1.08 and avg > 0:
        return "good"
    if pf is not None and avg is not None and pf >= 1.02 and avg >= 0:
        return "medium"
    return "weak"


def build_ml_v3_threshold_report(
    rows: list[dict[str, Any]],
    y_true: list[int],
    probabilities: list[float],
    *,
    thresholds: list[float] | None = None,
    min_signals: int = 30,
) -> list[dict[str, Any]]:
    total = len(rows)
    report: list[dict[str, Any]] = []
    for threshold in thresholds or EVALUATION_THRESHOLDS:
        selected = [(row, label, probability) for row, label, probability in zip(rows, y_true, probabilities) if probability >= threshold]
        rejected = [(row, label, probability) for row, label, probability in zip(rows, y_true, probabilities) if probability < threshold]
        selected_rows = [item[0] for item in selected]
        rejected_rows = [item[0] for item in rejected]
        selected_probs = [item[2] for item in selected]
        metrics = _pnl(selected_rows)
        signals = len(selected_rows)
        coverage = _round(signals / total * 100, 2) if total else 0.0
        avoided_losses = sum(1 for row in rejected_rows if (_to_float(row.get("trade_return_pct")) or 0.0) < 0)
        missed_wins = sum(1 for row in rejected_rows if (_to_float(row.get("trade_return_pct")) or 0.0) > 0)
        report.append(
            {
                "threshold_pct": _round(threshold * 100, 1),
                "signals": signals,
                "selected_samples": signals,
                "coverage_pct": coverage,
                "avg_probability_pct": _round(sum(selected_probs) / signals * 100, 2) if signals else None,
                "hit_rate_pct": _rate(sum(item[1] for item in selected), signals),
                "avg_trade_return_pct": metrics.get("avg_trade_return_pct"),
                "profit_factor": metrics.get("profit_factor"),
                "win_rate_pct": metrics.get("win_rate_pct"),
                "stop_hit_rate_pct": metrics.get("stop_hit_rate_pct"),
                "target_hit_rate_pct": metrics.get("target_hit_rate_pct"),
                "avoided_losses": avoided_losses,
                "missed_wins": missed_wins,
                "quality_label": _quality(signals, metrics.get("profit_factor"), metrics.get("avg_trade_return_pct"), coverage, min_signals),
            }
        )
    return report


def _ordered_dataset(dataset: dict[str, Any], label: str) -> tuple[list[list[float]], list[int], list[dict[str, Any]], list[str]]:
    X = dataset.get("X") or []
    y = [int(value) for value in (dataset.get("labels") or {}).get(label, [])]
    rows = dataset.get("rows") or []
    dates = [str(value or "") for value in dataset.get("dates") or []]
    order = sorted(range(len(X)), key=lambda index: dates[index])
    return [X[i] for i in order], [y[i] for i in order], [rows[i] for i in order], [dates[i] for i in order]


def evaluate_ml_v3_consumer_candidate_model(
    db: Session,
    *,
    max_tickers: int = 120,
    max_samples: int = 10000,
    min_history: int = 80,
    horizon: int = 30,
    policy_id: str = DEFAULT_POLICY_ID,
    label: str = "positive_trade_return",
    test_size: float = 0.25,
    commission_bps: float = 10.0,
    slippage_bps: float = 5.0,
    include_watch_candidates: bool = False,
) -> dict[str, Any]:
    warnings: list[str] = []
    limitations = [
        "Research-only ML v3 evaluation; production consumer logic is unchanged.",
        "Time split reduces leakage but does not replace walk-forward validation.",
        "Historical consumer candidates are proxy reconstructed.",
    ]
    if label not in SUPPORTED_LABELS:
        return {"ok": False, "mode": "ml_v3_consumer_candidate_evaluation", "label": label, "message": f"Unsupported label. Supported labels: {sorted(SUPPORTED_LABELS)}"}
    dataset = build_ml_v3_consumer_candidate_dataset(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        min_history=min_history,
        horizon=horizon,
        policy_id=policy_id,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        include_watch_candidates=include_watch_candidates,
    )
    warnings.extend(dataset.get("warnings") or [])
    if not dataset.get("ok"):
        return {"ok": False, "mode": "ml_v3_consumer_candidate_evaluation", "label": label, "dataset_summary": dataset.get("summary") or {}, "warnings": warnings + ["Could not build ML v3 consumer candidate dataset."], "limitations": limitations}

    X, y, rows, dates = _ordered_dataset(dataset, label)
    split_index = int(len(X) * (1.0 - test_size))
    split_index = max(1, min(len(X) - 1, split_index))
    X_train, X_test = X[:split_index], X[split_index:]
    y_train, y_test = y[:split_index], y[split_index:]
    rows_test = rows[split_index:]
    train_dates, test_dates = dates[:split_index], dates[split_index:]
    if len(set(y_train)) < 2 or len(set(y_test)) < 2:
        return {
            "ok": False,
            "mode": "ml_v3_consumer_candidate_evaluation",
            "label": label,
            "message": "Train or test split has only one class.",
            "dataset_summary": dataset.get("summary") or {},
            "train_period": _period(train_dates),
            "test_period": _period(test_dates),
            "warnings": warnings + ["Use more samples/tickers or another label."],
            "limitations": limitations,
        }
    model, error = train_ml_v2_classifier(X_train, y_train)
    if model is None:
        return {"ok": False, "mode": "ml_v3_consumer_candidate_evaluation", "label": label, "message": error or "Could not train ML v3 classifier.", "warnings": warnings, "limitations": limitations}
    probabilities = predict_ml_v2_probabilities(model, X_test)
    baseline = _pnl(rows_test)
    metrics = {
        "auc": _safe_auc(y_test, probabilities),
        "brier": _brier(y_test, probabilities),
        "baseline_positive_rate_pct": _rate(sum(y_test), len(y_test)),
        "test_baseline_avg_trade_return_pct": baseline.get("avg_trade_return_pct"),
        "test_baseline_profit_factor": baseline.get("profit_factor"),
        "test_baseline_win_rate_pct": baseline.get("win_rate_pct"),
        "test_baseline_stop_hit_rate_pct": baseline.get("stop_hit_rate_pct"),
    }
    return {
        "ok": True,
        "mode": "ml_v3_consumer_candidate_evaluation",
        "label": label,
        "dataset_summary": dataset.get("summary") or {},
        "train_period": _period(train_dates),
        "test_period": _period(test_dates),
        "metrics": metrics,
        "threshold_report": build_ml_v3_threshold_report(rows_test, y_test, probabilities),
        "feature_importance": ml_v2_feature_importance(model, dataset.get("feature_names") or []),
        "warnings": warnings,
        "limitations": limitations,
    }


def _gate_result(
    *,
    test_rows: list[dict[str, Any]],
    probabilities: list[float],
    threshold: float,
    gate_mode: str,
    min_signals: int,
) -> dict[str, Any]:
    baseline = _pnl(test_rows)
    passed = [row for row, probability in zip(test_rows, probabilities) if probability >= threshold]
    rejected = [row for row, probability in zip(test_rows, probabilities) if probability < threshold]
    selected = test_rows if gate_mode == "diagnostic_only" else passed
    selected_metrics = _pnl(selected)
    rejected_metrics = _pnl(rejected)
    selected_count = len(selected)
    coverage = _round(selected_count / len(test_rows) * 100, 2) if test_rows else 0.0
    row = {
        "gate_mode": gate_mode,
        "threshold_pct": _round(threshold * 100, 1),
        "baseline_samples": len(test_rows),
        "selected_samples": selected_count,
        "filtered_samples": 0 if gate_mode == "diagnostic_only" else len(rejected),
        "coverage_pct": coverage,
        "baseline_avg_trade_return_pct": baseline.get("avg_trade_return_pct"),
        "baseline_profit_factor": baseline.get("profit_factor"),
        "selected_avg_trade_return_pct": selected_metrics.get("avg_trade_return_pct"),
        "selected_profit_factor": selected_metrics.get("profit_factor"),
        "selected_win_rate_pct": selected_metrics.get("win_rate_pct"),
        "selected_stop_hit_rate_pct": selected_metrics.get("stop_hit_rate_pct"),
        "selected_target_hit_rate_pct": selected_metrics.get("target_hit_rate_pct"),
        "avg_trade_return_delta_pct": _metric_delta(selected_metrics, baseline, "avg_trade_return_pct"),
        "profit_factor_delta": _metric_delta(selected_metrics, baseline, "profit_factor"),
        "win_rate_delta_pct": _metric_delta(selected_metrics, baseline, "win_rate_pct"),
        "stop_hit_delta_pct": _metric_delta(selected_metrics, baseline, "stop_hit_rate_pct"),
        "target_hit_delta_pct": _metric_delta(selected_metrics, baseline, "target_hit_rate_pct"),
        "avoided_losses": sum(1 for item in rejected if (_to_float(item.get("trade_return_pct")) or 0.0) < 0),
        "missed_wins": sum(1 for item in rejected if (_to_float(item.get("trade_return_pct")) or 0.0) > 0),
        "warnings": [],
    }
    if gate_mode == "diagnostic_only":
        passed_metrics = _pnl(passed)
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
    if selected_count < min_signals:
        row["warnings"].append(f"selected_samples below min_signals={min_signals}")
    return row


def score_ml_v3_walk_forward_result(row: dict[str, Any], *, folds: int, min_signals: int) -> float:
    avg_return = _to_float(row.get("avg_selected_trade_return_pct")) or 0.0
    avg_pf = _to_float(row.get("avg_selected_profit_factor")) or 0.0
    avg_delta = _to_float(row.get("avg_trade_return_delta_pct")) or 0.0
    pf_delta = _to_float(row.get("avg_profit_factor_delta")) or 0.0
    stable = _to_float(row.get("stable_positive_rate_pct")) or 0.0
    positive_folds = int(row.get("positive_folds") or 0)
    negative_folds = int(row.get("negative_folds") or 0)
    stop_delta = _to_float(row.get("avg_stop_hit_delta_pct")) or 0.0
    selected = int(row.get("total_selected_samples") or 0)
    coverage = _to_float(row.get("avg_coverage_pct")) or 0.0
    folds_with = int(row.get("folds_with_signals") or 0)
    score = avg_return * 25 + max(0.0, avg_pf - 1.0) * 35 + avg_delta * 20 + pf_delta * 25 + stable * 0.25
    score += positive_folds * 2 - negative_folds * 2 + max(0.0, -stop_delta) * 0.7
    if selected < min_signals:
        score -= 40
    if coverage < 5:
        score -= 30
    elif coverage < 10:
        score -= 20
    if folds_with < max(2, folds // 2):
        score -= 25
    return _round(max(-100.0, min(100.0, score)), 2) or 0.0


def _wf_quality(row: dict[str, Any], *, folds: int, min_signals: int) -> str:
    selected = int(row.get("total_selected_samples") or 0)
    coverage = _to_float(row.get("avg_coverage_pct")) or 0.0
    folds_with = int(row.get("folds_with_signals") or 0)
    avg_return = _to_float(row.get("avg_selected_trade_return_pct")) or 0.0
    avg_pf = _to_float(row.get("avg_selected_profit_factor")) or 0.0
    stable = _to_float(row.get("stable_positive_rate_pct")) or 0.0
    if selected < min_signals or coverage < 5 or folds_with < max(1, folds // 2):
        return "unstable"
    if avg_return > 0 and avg_pf >= 1.08 and stable >= 60 and folds_with >= max(2, folds // 2):
        return "stable"
    if avg_return > 0 and avg_pf >= 1.03:
        return "promising"
    return "weak"


def _aggregate_folds(folds_data: list[dict[str, Any]], *, thresholds: list[float], gate_modes: list[str], min_signals: int, folds_requested: int) -> list[dict[str, Any]]:
    completed = [fold for fold in folds_data if fold.get("gate_results")]
    rows: list[dict[str, Any]] = []
    for mode in gate_modes:
        for threshold in thresholds:
            threshold_pct = _round(threshold * 100, 1)
            fold_rows = [
                row
                for fold in completed
                for row in fold.get("gate_results") or []
                if row.get("gate_mode") == mode and _to_float(row.get("threshold_pct")) == threshold_pct
            ]
            signal_rows = [row for row in fold_rows if int(row.get("selected_samples") or 0) > 0]
            returns = [_to_float(row.get("selected_avg_trade_return_pct")) for row in signal_rows if _to_float(row.get("selected_avg_trade_return_pct")) is not None]
            pfs = [_to_float(row.get("selected_profit_factor")) for row in signal_rows if _to_float(row.get("selected_profit_factor")) is not None]
            wins = [_to_float(row.get("selected_win_rate_pct")) for row in signal_rows if _to_float(row.get("selected_win_rate_pct")) is not None]
            stops = [_to_float(row.get("selected_stop_hit_rate_pct")) for row in signal_rows if _to_float(row.get("selected_stop_hit_rate_pct")) is not None]
            baseline_returns = [_to_float(row.get("baseline_avg_trade_return_pct")) for row in fold_rows if _to_float(row.get("baseline_avg_trade_return_pct")) is not None]
            deltas = [_to_float(row.get("avg_trade_return_delta_pct")) for row in signal_rows if _to_float(row.get("avg_trade_return_delta_pct")) is not None]
            pf_deltas = [_to_float(row.get("profit_factor_delta")) for row in signal_rows if _to_float(row.get("profit_factor_delta")) is not None]
            stop_deltas = [_to_float(row.get("stop_hit_delta_pct")) for row in signal_rows if _to_float(row.get("stop_hit_delta_pct")) is not None]
            coverage = [_to_float(row.get("coverage_pct")) or 0.0 for row in fold_rows]
            positive_folds = sum(1 for value in returns if value > 0)
            negative_folds = sum(1 for value in returns if value <= 0)
            item = {
                "gate_mode": mode,
                "threshold_pct": threshold_pct,
                "folds_with_signals": len(signal_rows),
                "folds_total": len(completed),
                "total_selected_samples": sum(int(row.get("selected_samples") or 0) for row in fold_rows),
                "avg_coverage_pct": _round(sum(coverage) / len(coverage), 2) if coverage else 0.0,
                "avg_selected_trade_return_pct": _round(sum(returns) / len(returns), 2) if returns else None,
                "median_selected_trade_return_pct": _round(median(returns), 2) if returns else None,
                "avg_selected_profit_factor": _round(sum(pfs) / len(pfs), 3) if pfs else None,
                "avg_selected_win_rate_pct": _round(sum(wins) / len(wins), 2) if wins else None,
                "avg_selected_stop_hit_rate_pct": _round(sum(stops) / len(stops), 2) if stops else None,
                "avg_baseline_trade_return_pct": _round(sum(baseline_returns) / len(baseline_returns), 2) if baseline_returns else None,
                "avg_trade_return_delta_pct": _round(sum(deltas) / len(deltas), 3) if deltas else None,
                "avg_profit_factor_delta": _round(sum(pf_deltas) / len(pf_deltas), 3) if pf_deltas else None,
                "avg_stop_hit_delta_pct": _round(sum(stop_deltas) / len(stop_deltas), 2) if stop_deltas else None,
                "positive_folds": positive_folds,
                "negative_folds": negative_folds,
                "stable_positive_rate_pct": _rate(positive_folds, len(signal_rows)) if signal_rows else 0.0,
                "warnings": [],
            }
            item["score"] = score_ml_v3_walk_forward_result(item, folds=folds_requested, min_signals=min_signals)
            item["quality_label"] = _wf_quality(item, folds=folds_requested, min_signals=min_signals)
            rows.append(item)
    quality_rank = {"stable": 3, "promising": 2, "weak": 1, "unstable": 0}
    mode_rank = {"hard_gate": 3, "soft_downgrade": 2, "diagnostic_only": 1}
    rows.sort(
        key=lambda row: (
            quality_rank.get(str(row.get("quality_label") or ""), 0),
            _to_float(row.get("score")) if _to_float(row.get("score")) is not None else -999,
            mode_rank.get(str(row.get("gate_mode") or ""), 0),
            _to_float(row.get("avg_selected_profit_factor")) if _to_float(row.get("avg_selected_profit_factor")) is not None else -999,
        ),
        reverse=True,
    )
    return rows


def _recommendation(best: dict[str, Any] | None, *, folds_completed: int) -> str:
    if folds_completed <= 0:
        return "needs_more_data"
    if not best:
        return "reject"
    quality = str(best.get("quality_label") or "")
    avg_return = _to_float(best.get("avg_selected_trade_return_pct")) or 0.0
    avg_pf = _to_float(best.get("avg_selected_profit_factor")) or 0.0
    stable = _to_float(best.get("stable_positive_rate_pct")) or 0.0
    if quality == "stable" and avg_pf >= 1.08 and avg_return > 0 and stable >= 60:
        return "promising_ml_v3_gate"
    if avg_return > 0 and avg_pf >= 1.0:
        return "research_only"
    return "reject"


def build_ml_v3_consumer_candidate_walk_forward(
    db: Session,
    *,
    max_tickers: int = 120,
    max_samples: int = 10000,
    min_history: int = 80,
    horizon: int = 30,
    policy_id: str = DEFAULT_POLICY_ID,
    label: str = "positive_trade_return",
    folds: int = 4,
    train_ratio: float = 0.6,
    min_train_samples: int = 300,
    min_test_samples: int = 100,
    thresholds: list[float] | None = None,
    gate_modes: list[str] | None = None,
    commission_bps: float = 10.0,
    slippage_bps: float = 5.0,
    min_signals: int = 30,
    include_watch_candidates: bool = False,
) -> dict[str, Any]:
    threshold_values = thresholds or list(WALK_FORWARD_THRESHOLDS)
    mode_values = [mode for mode in (gate_modes or list(DEFAULT_GATE_MODES)) if mode in VALID_GATE_MODES] or list(DEFAULT_GATE_MODES)
    warnings: list[str] = []
    limitations = [
        "Leakage-safe by fold: each ML v3 model trains only on earlier consumer candidates.",
        "ML v3 is research-only and is not integrated into production consumer signals.",
        "Historical consumer candidate actions are proxy reconstructed.",
    ]
    if label not in SUPPORTED_LABELS:
        return {"ok": False, "mode": "ml_v3_consumer_candidate_walk_forward", "label": label, "message": f"Unsupported label. Supported labels: {sorted(SUPPORTED_LABELS)}", "summary": {"recommendation": "needs_more_data"}, "best_results": [], "results": [], "folds": [], "limitations": limitations}
    dataset = build_ml_v3_consumer_candidate_dataset(
        db=db,
        max_tickers=max_tickers,
        max_samples=max_samples,
        min_history=min_history,
        horizon=horizon,
        policy_id=policy_id,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        include_watch_candidates=include_watch_candidates,
    )
    warnings.extend(dataset.get("warnings") or [])
    if not dataset.get("ok"):
        return {"ok": True, "mode": "ml_v3_consumer_candidate_walk_forward", "summary": {"samples": 0, "recommendation": "needs_more_data", "warnings": warnings}, "best_results": [], "results": [], "folds": [], "limitations": limitations}
    X, y, rows, dates = _ordered_dataset(dataset, label)
    ranges = build_gate_walk_forward_ranges(len(X), folds, train_ratio, min_train_samples, min_test_samples)
    if not ranges:
        warnings.append("Not enough samples to create requested walk-forward folds.")
    fold_results: list[dict[str, Any]] = []
    for fold_index, (train_start, train_end, test_end) in enumerate(ranges, start=1):
        X_train, X_test = X[train_start:train_end], X[train_end:test_end]
        y_train, y_test = y[train_start:train_end], y[train_end:test_end]
        rows_test = rows[train_end:test_end]
        train_dates, test_dates = dates[train_start:train_end], dates[train_end:test_end]
        fold_warnings: list[str] = []
        baseline = _pnl(rows_test)
        if len(set(y_train)) < 2 or len(set(y_test)) < 2:
            fold_warnings.append("fold skipped: train or test split has only one class")
            fold_results.append({"fold": fold_index, "train_period": _period(train_dates), "test_period": _period(test_dates), "baseline_metrics": baseline, "gate_results": [], "warnings": fold_warnings})
            continue
        model, error = train_ml_v2_classifier(X_train, y_train)
        if model is None:
            fold_warnings.append(error or "fold skipped: model training failed")
            fold_results.append({"fold": fold_index, "train_period": _period(train_dates), "test_period": _period(test_dates), "baseline_metrics": baseline, "gate_results": [], "warnings": fold_warnings})
            continue
        probabilities = predict_ml_v2_probabilities(model, X_test)
        gate_results = [
            _gate_result(test_rows=rows_test, probabilities=probabilities, threshold=threshold, gate_mode=mode, min_signals=min_signals)
            for threshold in threshold_values
            for mode in mode_values
        ]
        fold_results.append(
            {
                "fold": fold_index,
                "train_period": _period(train_dates),
                "test_period": _period(test_dates),
                "train_positive_rate_pct": _rate(sum(y_train), len(y_train)),
                "test_positive_rate_pct": _rate(sum(y_test), len(y_test)),
                "auc": _safe_auc(y_test, probabilities),
                "brier": _brier(y_test, probabilities),
                "baseline_metrics": baseline,
                "gate_results": gate_results,
                "warnings": fold_warnings,
            }
        )
    completed = [fold for fold in fold_results if fold.get("gate_results")]
    aggregate = _aggregate_folds(fold_results, thresholds=threshold_values, gate_modes=mode_values, min_signals=min_signals, folds_requested=folds)
    best = aggregate[0] if aggregate else None
    summary = {
        "samples": len(X),
        "tickers_used": (dataset.get("summary") or {}).get("tickers_used"),
        "folds_requested": folds,
        "folds_completed": len(completed),
        "thresholds": [_round(value * 100, 1) for value in threshold_values],
        "gate_modes": mode_values,
        "best_gate_mode": best.get("gate_mode") if best else None,
        "best_threshold_pct": best.get("threshold_pct") if best else None,
        "best_score": best.get("score") if best else None,
        "best_quality_label": best.get("quality_label") if best else None,
        "recommendation": _recommendation(best, folds_completed=len(completed)),
        "warnings": warnings,
    }
    return {
        "ok": True,
        "mode": "ml_v3_consumer_candidate_walk_forward",
        "label": label,
        "summary": summary,
        "best_results": aggregate[:10],
        "results": aggregate,
        "folds": fold_results,
        "limitations": limitations,
    }
