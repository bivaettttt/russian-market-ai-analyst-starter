from __future__ import annotations

from statistics import median
from typing import Any

from sqlalchemy.orm import Session

from app.services.adaptive_trade_calibration import aggregate_trade_pnl_metrics
from app.services.ml_probability_engine import _brier, _safe_auc
from app.services.ml_v2_dataset import DEFAULT_POLICY_ID, build_ml_v2_trade_dataset
from app.services.ml_v2_evaluation import SUPPORTED_LABELS, predict_ml_v2_probabilities, train_ml_v2_classifier
from app.services.ml_v2_gate_impact_evaluation import (
    DEFAULT_GATE_MODES,
    DEFAULT_THRESHOLDS,
    VALID_GATE_MODES,
    _impact_row,
    _pnl_rows,
    _round,
    _to_float,
    parse_gate_impact_thresholds,
    parse_gate_modes,
)
from app.services.ml_v2_high_confidence_validation import _fold_ranges


def build_gate_walk_forward_ranges(
    total: int,
    folds: int,
    train_ratio: float,
    min_train_samples: int,
    min_test_samples: int,
) -> list[tuple[int, int, int]]:
    return _fold_ranges(total, folds, train_ratio, min_train_samples, min_test_samples)


def _rate(part: int, total: int) -> float | None:
    return _round(part / total * 100, 2) if total else None


def _period(dates: list[str]) -> dict[str, Any]:
    return {
        "first_date": dates[0] if dates else None,
        "last_date": dates[-1] if dates else None,
        "samples": len(dates),
    }


def _baseline_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = aggregate_trade_pnl_metrics(_pnl_rows(rows))
    metrics["samples"] = len(rows)
    return metrics


def score_gate_walk_forward_summary(
    row: dict[str, Any],
    *,
    folds_requested: int,
    min_signals: int,
) -> float:
    avg_return = _to_float(row.get("avg_selected_trade_return_pct")) or 0.0
    avg_pf = _to_float(row.get("avg_selected_profit_factor")) or 0.0
    avg_delta = _to_float(row.get("avg_trade_return_delta_pct")) or 0.0
    pf_delta = _to_float(row.get("avg_profit_factor_delta")) or 0.0
    stable_rate = _to_float(row.get("stable_positive_rate_pct")) or 0.0
    positive_folds = int(row.get("positive_folds") or 0)
    negative_folds = int(row.get("negative_folds") or 0)
    stop_delta = _to_float(row.get("avg_stop_hit_delta_pct")) or 0.0
    total_selected = int(row.get("total_selected_samples") or 0)
    avg_coverage = _to_float(row.get("avg_coverage_pct")) or 0.0
    folds_with_signals = int(row.get("folds_with_signals") or 0)

    score = 0.0
    score += avg_return * 25.0
    score += max(0.0, avg_pf - 1.0) * 35.0
    score += avg_delta * 20.0
    score += pf_delta * 25.0
    score += stable_rate * 0.25
    score += positive_folds * 2.0
    score -= negative_folds * 2.0
    score += max(0.0, -stop_delta) * 0.7

    if total_selected < min_signals:
        score -= 40.0
    if avg_coverage < 5:
        score -= 30.0
    elif avg_coverage < 10:
        score -= 20.0
    if folds_with_signals < max(2, folds_requested // 2):
        score -= 25.0
    return _round(max(-100.0, min(100.0, score)), 2) or 0.0


def classify_gate_walk_forward_quality(
    row: dict[str, Any],
    *,
    folds_requested: int,
    min_signals: int,
) -> str:
    total_selected = int(row.get("total_selected_samples") or 0)
    folds_with_signals = int(row.get("folds_with_signals") or 0)
    avg_coverage = _to_float(row.get("avg_coverage_pct")) or 0.0
    avg_return = _to_float(row.get("avg_selected_trade_return_pct")) or 0.0
    avg_pf = _to_float(row.get("avg_selected_profit_factor")) or 0.0
    stable_rate = _to_float(row.get("stable_positive_rate_pct")) or 0.0

    if total_selected < min_signals or avg_coverage < 5 or folds_with_signals < max(1, folds_requested // 2):
        return "unstable"
    if avg_return > 0 and avg_pf >= 1.08 and stable_rate >= 60 and folds_with_signals >= max(2, folds_requested // 2):
        return "stable"
    if avg_return > 0 and avg_pf >= 1.03:
        return "promising"
    return "weak"


def _evaluate_gate_rows(
    *,
    test_rows: list[dict[str, Any]],
    probabilities: list[float],
    thresholds: list[float],
    gate_modes: list[str],
    min_signals: int,
) -> list[dict[str, Any]]:
    rows = [dict(row, ml_v2_probability_pct=_round(probability * 100, 2)) for row, probability in zip(test_rows, probabilities)]
    baseline = _baseline_metrics(rows)
    results: list[dict[str, Any]] = []
    for threshold in thresholds:
        normalized_threshold = threshold / 100.0 if threshold > 1 else threshold
        threshold_pct = normalized_threshold * 100
        passed = [row for row in rows if (_to_float(row.get("ml_v2_probability_pct")) or 0.0) >= threshold_pct]
        rejected = [row for row in rows if (_to_float(row.get("ml_v2_probability_pct")) or 0.0) < threshold_pct]
        if "diagnostic_only" in gate_modes:
            diagnostic = _impact_row(
                gate_mode="diagnostic_only",
                threshold=normalized_threshold,
                baseline_rows=rows,
                selected_rows=passed,
                filtered_rows=rejected,
                baseline_metrics=baseline,
                min_signals=min_signals,
            )
            passed_metrics = _baseline_metrics(passed)
            rejected_metrics = _baseline_metrics(rejected)
            diagnostic.update(
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
            results.append(diagnostic)
        for mode in gate_modes:
            if mode == "diagnostic_only":
                continue
            results.append(
                _impact_row(
                    gate_mode=mode,
                    threshold=normalized_threshold,
                    baseline_rows=rows,
                    selected_rows=passed,
                    filtered_rows=rejected,
                    baseline_metrics=baseline,
                    min_signals=min_signals,
                )
            )
    return results


def aggregate_gate_walk_forward_results(
    folds: list[dict[str, Any]],
    *,
    thresholds: list[float],
    gate_modes: list[str],
    min_signals: int,
) -> list[dict[str, Any]]:
    completed = [fold for fold in folds if fold.get("gate_results")]
    folds_requested = len(completed)
    rows: list[dict[str, Any]] = []

    for gate_mode in gate_modes:
        for threshold in thresholds:
            threshold_pct = _round((threshold / 100.0 if threshold > 1 else threshold) * 100, 1)
            fold_rows = []
            for fold in completed:
                for row in fold.get("gate_results") or []:
                    if row.get("gate_mode") == gate_mode and _to_float(row.get("threshold_pct")) == threshold_pct:
                        fold_rows.append(row)
                        break

            signal_rows = [row for row in fold_rows if int(row.get("selected_samples") or 0) > 0]
            selected_returns = [
                _to_float(row.get("selected_avg_trade_return_pct"))
                for row in signal_rows
                if _to_float(row.get("selected_avg_trade_return_pct")) is not None
            ]
            selected_pfs = [
                _to_float(row.get("selected_profit_factor"))
                for row in signal_rows
                if _to_float(row.get("selected_profit_factor")) is not None
            ]
            selected_wins = [
                _to_float(row.get("selected_win_rate_pct"))
                for row in signal_rows
                if _to_float(row.get("selected_win_rate_pct")) is not None
            ]
            selected_stops = [
                _to_float(row.get("selected_stop_hit_rate_pct"))
                for row in signal_rows
                if _to_float(row.get("selected_stop_hit_rate_pct")) is not None
            ]
            baseline_returns = [
                _to_float(row.get("baseline_avg_trade_return_pct"))
                for row in fold_rows
                if _to_float(row.get("baseline_avg_trade_return_pct")) is not None
            ]
            return_deltas = [
                _to_float(row.get("avg_trade_return_delta_pct"))
                for row in signal_rows
                if _to_float(row.get("avg_trade_return_delta_pct")) is not None
            ]
            pf_deltas = [
                _to_float(row.get("profit_factor_delta"))
                for row in signal_rows
                if _to_float(row.get("profit_factor_delta")) is not None
            ]
            win_deltas = [
                _to_float(row.get("win_rate_delta_pct"))
                for row in signal_rows
                if _to_float(row.get("win_rate_delta_pct")) is not None
            ]
            stop_deltas = [
                _to_float(row.get("stop_hit_delta_pct"))
                for row in signal_rows
                if _to_float(row.get("stop_hit_delta_pct")) is not None
            ]
            coverage = [_to_float(row.get("coverage_pct")) or 0.0 for row in fold_rows]
            positive_folds = sum(1 for value in selected_returns if value > 0)
            negative_folds = sum(1 for value in selected_returns if value <= 0)
            item = {
                "gate_mode": gate_mode,
                "threshold_pct": threshold_pct,
                "folds_with_signals": len(signal_rows),
                "folds_total": len(completed),
                "total_selected_samples": sum(int(row.get("selected_samples") or 0) for row in fold_rows),
                "avg_coverage_pct": _round(sum(coverage) / len(coverage), 2) if coverage else 0.0,
                "avg_selected_trade_return_pct": _round(sum(selected_returns) / len(selected_returns), 2) if selected_returns else None,
                "median_selected_trade_return_pct": _round(median(selected_returns), 2) if selected_returns else None,
                "avg_selected_profit_factor": _round(sum(selected_pfs) / len(selected_pfs), 3) if selected_pfs else None,
                "avg_selected_win_rate_pct": _round(sum(selected_wins) / len(selected_wins), 2) if selected_wins else None,
                "avg_selected_stop_hit_rate_pct": _round(sum(selected_stops) / len(selected_stops), 2) if selected_stops else None,
                "avg_baseline_trade_return_pct": _round(sum(baseline_returns) / len(baseline_returns), 2) if baseline_returns else None,
                "avg_trade_return_delta_pct": _round(sum(return_deltas) / len(return_deltas), 3) if return_deltas else None,
                "avg_profit_factor_delta": _round(sum(pf_deltas) / len(pf_deltas), 3) if pf_deltas else None,
                "avg_win_rate_delta_pct": _round(sum(win_deltas) / len(win_deltas), 2) if win_deltas else None,
                "avg_stop_hit_delta_pct": _round(sum(stop_deltas) / len(stop_deltas), 2) if stop_deltas else None,
                "positive_folds": positive_folds,
                "negative_folds": negative_folds,
                "stable_positive_rate_pct": _rate(positive_folds, len(signal_rows)) if signal_rows else 0.0,
                "avg_avoided_losses": _round(
                    sum(int(row.get("avoided_losses") or 0) for row in fold_rows) / len(fold_rows), 2
                )
                if fold_rows
                else 0.0,
                "avg_missed_wins": _round(
                    sum(int(row.get("missed_wins") or 0) for row in fold_rows) / len(fold_rows), 2
                )
                if fold_rows
                else 0.0,
                "warnings": [],
            }
            item["score"] = score_gate_walk_forward_summary(item, folds_requested=max(1, folds_requested), min_signals=min_signals)
            item["quality_label"] = classify_gate_walk_forward_quality(
                item,
                folds_requested=max(1, folds_requested),
                min_signals=min_signals,
            )
            if gate_mode == "soft_downgrade":
                item["warnings"].append("soft_downgrade assumes downgraded trades are not opened.")
            rows.append(item)

    quality_rank = {"stable": 3, "promising": 2, "weak": 1, "unstable": 0}
    mode_rank = {"hard_gate": 3, "soft_downgrade": 2, "diagnostic_only": 1}
    rows.sort(
        key=lambda row: (
            quality_rank.get(str(row.get("quality_label") or ""), 0),
            _to_float(row.get("score")) or -999,
            mode_rank.get(str(row.get("gate_mode") or ""), 0),
            _to_float(row.get("avg_selected_profit_factor")) or -999,
            _to_float(row.get("avg_selected_trade_return_pct")) or -999,
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
    stable_rate = _to_float(best.get("stable_positive_rate_pct")) or 0.0
    if quality == "stable" and avg_pf >= 1.08 and avg_return > 0 and stable_rate >= 60:
        return "promising_gate"
    if quality in {"stable", "promising"} and avg_return > 0 and avg_pf >= 1.03:
        return "research_only"
    return "reject"


def build_ml_v2_gate_walk_forward(
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
    min_train_samples: int = 500,
    min_test_samples: int = 150,
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
    warnings: list[str] = []

    if label not in SUPPORTED_LABELS:
        return {
            "ok": False,
            "mode": "ml_v2_gate_walk_forward",
            "message": f"Unsupported label. Supported labels: {sorted(SUPPORTED_LABELS)}",
            "summary": {"folds_completed": 0, "recommendation": "needs_more_data"},
            "best_results": [],
            "results": [],
            "folds": [],
            "limitations": [],
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
    warnings.extend(dataset.get("warnings") or [])
    if not dataset.get("ok"):
        return {
            "ok": True,
            "mode": "ml_v2_gate_walk_forward",
            "summary": {
                "samples": 0,
                "tickers_used": 0,
                "folds_requested": folds,
                "folds_completed": 0,
                "thresholds": [_round(value * 100, 1) for value in threshold_values],
                "gate_modes": gate_mode_values,
                "recommendation": "needs_more_data",
                "warnings": warnings + ["Dataset has no samples."],
            },
            "best_results": [],
            "results": [],
            "folds": [],
            "limitations": [],
        }

    X = dataset["X"]
    y = [int(value) for value in dataset["labels"][label]]
    rows = dataset["rows"]
    dates = dataset["dates"]
    order = sorted(range(len(X)), key=lambda index: dates[index])
    X = [X[index] for index in order]
    y = [y[index] for index in order]
    rows = [rows[index] for index in order]
    dates = [dates[index] for index in order]

    ranges = build_gate_walk_forward_ranges(len(X), folds, train_ratio, min_train_samples, min_test_samples)
    if not ranges:
        warnings.append("Not enough samples to create requested walk-forward folds.")

    fold_results: list[dict[str, Any]] = []
    for fold_index, (train_start, train_end, test_end) in enumerate(ranges, start=1):
        X_train, X_test = X[train_start:train_end], X[train_end:test_end]
        y_train, y_test = y[train_start:train_end], y[train_end:test_end]
        rows_test = rows[train_end:test_end]
        train_dates = dates[train_start:train_end]
        test_dates = dates[train_end:test_end]
        fold_warnings: list[str] = []
        baseline = _baseline_metrics(rows_test)

        if len(set(y_train)) < 2 or len(set(y_test)) < 2:
            fold_warnings.append("fold skipped: train or test split has only one class")
            fold_results.append(
                {
                    "fold": fold_index,
                    "train_period": _period(train_dates),
                    "test_period": _period(test_dates),
                    "baseline_metrics": baseline,
                    "gate_results": [],
                    "warnings": fold_warnings,
                }
            )
            continue

        model, error = train_ml_v2_classifier(X_train, y_train)
        if model is None:
            fold_warnings.append(error or "fold skipped: model training failed")
            fold_results.append(
                {
                    "fold": fold_index,
                    "train_period": _period(train_dates),
                    "test_period": _period(test_dates),
                    "baseline_metrics": baseline,
                    "gate_results": [],
                    "warnings": fold_warnings,
                }
            )
            continue

        probabilities = predict_ml_v2_probabilities(model, X_test)
        gate_results = _evaluate_gate_rows(
            test_rows=rows_test,
            probabilities=probabilities,
            thresholds=threshold_values,
            gate_modes=gate_mode_values,
            min_signals=min_signals,
        )
        quality_rank = {"good": 3, "medium": 2, "weak": 1, "unstable": 0}
        best_fold_result = max(
            gate_results,
            key=lambda row: (
                quality_rank.get(str(row.get("quality_label") or ""), 0),
                _to_float(row.get("score")) or -999,
                _to_float(row.get("selected_profit_factor")) or -999,
            ),
            default=None,
        )
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
                "best_fold_result": best_fold_result,
                "warnings": fold_warnings,
            }
        )

    completed_folds = [fold for fold in fold_results if fold.get("gate_results")]
    aggregate = aggregate_gate_walk_forward_results(
        completed_folds,
        thresholds=threshold_values,
        gate_modes=gate_mode_values,
        min_signals=min_signals,
    )
    best = aggregate[0] if aggregate else None
    summary = {
        "samples": len(X),
        "tickers_used": len({row.get("ticker") for row in rows if row.get("ticker")}),
        "folds_requested": folds,
        "folds_completed": len(completed_folds),
        "thresholds": [_round((value / 100.0 if value > 1 else value) * 100, 1) for value in threshold_values],
        "gate_modes": gate_mode_values,
        "best_gate_mode": best.get("gate_mode") if best else None,
        "best_threshold_pct": best.get("threshold_pct") if best else None,
        "best_score": best.get("score") if best else None,
        "best_quality_label": best.get("quality_label") if best else None,
        "recommendation": _recommendation(best, folds_completed=len(completed_folds)),
        "warnings": warnings,
    }
    if len(completed_folds) < folds:
        summary["warnings"].append("Some folds were skipped or incomplete; inspect fold warnings.")

    return {
        "ok": True,
        "mode": "ml_v2_gate_walk_forward",
        "summary": summary,
        "best_results": aggregate[:10],
        "results": aggregate,
        "folds": fold_results,
        "limitations": [
            "Leakage-safe by fold: each model is trained only on earlier train samples and scored on future test samples.",
            "Labels are proxy daily-candle trade outcomes with simplified costs.",
            "Daily candles cannot fully resolve intraday target/stop ordering.",
            "High thresholds can have small-sample risk.",
            "This research result does not modify production consumer logic and still needs paper trading validation.",
        ],
    }


parse_gate_walk_forward_thresholds = parse_gate_impact_thresholds
parse_gate_walk_forward_modes = parse_gate_modes
