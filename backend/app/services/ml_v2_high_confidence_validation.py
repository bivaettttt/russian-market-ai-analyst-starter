from __future__ import annotations

from statistics import median
from typing import Any

from sqlalchemy.orm import Session

from app.services.consumer_signals import _round, _to_float
from app.services.ml_probability_engine import _brier, _safe_auc
from app.services.ml_v2_dataset import build_ml_v2_trade_dataset
from app.services.ml_v2_evaluation import (
    SUPPORTED_LABELS,
    build_ml_v2_threshold_report,
    ml_v2_feature_importance,
    predict_ml_v2_probabilities,
    train_ml_v2_classifier,
)


DEFAULT_THRESHOLDS = [0.50, 0.55, 0.60, 0.65, 0.70]


def parse_thresholds(value: str | None, default: list[float] | None = None) -> list[float]:
    if not value:
        return list(default or DEFAULT_THRESHOLDS)
    parsed: list[float] = []
    for raw in value.split(","):
        try:
            number = float(raw.strip())
        except ValueError:
            continue
        if 0.05 <= number <= 0.95:
            parsed.append(round(number, 4))
    unique = sorted(set(parsed))
    return unique or list(default or DEFAULT_THRESHOLDS)


def _rate(part: int, total: int) -> float | None:
    return _round(part / total * 100, 2) if total else None


def _period(dates: list[str]) -> dict[str, Any]:
    return {
        "first_date": dates[0] if dates else None,
        "last_date": dates[-1] if dates else None,
        "samples": len(dates),
    }


def _fold_ranges(total: int, folds: int, train_ratio: float, min_train_samples: int, min_test_samples: int) -> list[tuple[int, int, int]]:
    if total < min_train_samples + min_test_samples:
        return []
    initial_train = max(min_train_samples, int(total * train_ratio))
    remaining = total - initial_train
    if remaining < min_test_samples:
        return []
    fold_count = max(1, min(folds, remaining // min_test_samples))
    test_window = max(min_test_samples, remaining // fold_count)
    ranges: list[tuple[int, int, int]] = []
    train_end = initial_train
    for _ in range(fold_count):
        test_end = min(total, train_end + test_window)
        if test_end - train_end < min_test_samples:
            break
        ranges.append((0, train_end, test_end))
        train_end = test_end
        if train_end >= total:
            break
    return ranges


def score_threshold_summary(row: dict[str, Any], *, requested_folds: int) -> float:
    avg_return = _to_float(row.get("avg_trade_return_pct")) or 0.0
    avg_pf = _to_float(row.get("avg_profit_factor")) or 0.0
    stable_rate = _to_float(row.get("stable_positive_rate_pct")) or 0.0
    positive_folds = int(row.get("positive_folds") or 0)
    negative_folds = int(row.get("negative_folds") or 0)
    total_signals = int(row.get("total_signals") or 0)
    avg_coverage = _to_float(row.get("avg_coverage_pct")) or 0.0
    folds_with_signals = int(row.get("folds_with_signals") or 0)
    score = 0.0
    score += avg_return * 25.0
    score += max(0.0, avg_pf - 1.0) * 35.0
    score += stable_rate * 0.3
    score += positive_folds * 2.0
    score -= negative_folds * 2.0
    if total_signals < 50:
        score -= 20.0
    if avg_coverage < 5:
        score -= 15.0
    if folds_with_signals < max(2, requested_folds // 2):
        score -= 20.0
    return _round(max(-100.0, min(100.0, score)), 2) or 0.0


def threshold_quality_label(row: dict[str, Any], *, requested_folds: int) -> str:
    total_signals = int(row.get("total_signals") or 0)
    folds_with_signals = int(row.get("folds_with_signals") or 0)
    avg_return = _to_float(row.get("avg_trade_return_pct")) or 0.0
    avg_pf = _to_float(row.get("avg_profit_factor")) or 0.0
    stable_rate = _to_float(row.get("stable_positive_rate_pct")) or 0.0
    if total_signals < 30 or folds_with_signals < max(1, requested_folds // 2):
        return "unstable"
    if avg_return > 0 and avg_pf >= 1.08 and stable_rate >= 60 and total_signals >= 50:
        return "stable"
    if avg_return > 0 and avg_pf >= 1.03 and total_signals >= 30:
        return "promising"
    return "weak"


def aggregate_threshold_summary(folds: list[dict[str, Any]], thresholds: list[float]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    requested_folds = len(folds)
    for threshold in thresholds:
        threshold_pct = _round(threshold * 100, 1)
        rows = []
        for fold in folds:
            for row in fold.get("threshold_report") or []:
                if _to_float(row.get("threshold_pct")) == threshold_pct:
                    rows.append(row)
                    break
        signal_rows = [row for row in rows if int(row.get("signals") or 0) > 0]
        total_signals = sum(int(row.get("signals") or 0) for row in rows)
        avg_returns = [_to_float(row.get("avg_trade_return_pct")) for row in signal_rows if _to_float(row.get("avg_trade_return_pct")) is not None]
        profit_factors = [_to_float(row.get("profit_factor")) for row in signal_rows if _to_float(row.get("profit_factor")) is not None]
        win_rates = [_to_float(row.get("win_rate_pct")) for row in signal_rows if _to_float(row.get("win_rate_pct")) is not None]
        stop_rates = [_to_float(row.get("stop_hit_rate_pct")) for row in signal_rows if _to_float(row.get("stop_hit_rate_pct")) is not None]
        coverage = [_to_float(row.get("coverage_pct")) or 0.0 for row in rows]
        positive_folds = sum(1 for value in avg_returns if value > 0)
        negative_folds = sum(1 for value in avg_returns if value <= 0)
        item = {
            "threshold_pct": threshold_pct,
            "folds_with_signals": len(signal_rows),
            "total_signals": total_signals,
            "avg_coverage_pct": _round(sum(coverage) / len(coverage), 2) if coverage else 0.0,
            "avg_trade_return_pct": _round(sum(avg_returns) / len(avg_returns), 2) if avg_returns else None,
            "median_trade_return_pct": _round(median(avg_returns), 2) if avg_returns else None,
            "avg_profit_factor": _round(sum(profit_factors) / len(profit_factors), 3) if profit_factors else None,
            "avg_win_rate_pct": _round(sum(win_rates) / len(win_rates), 2) if win_rates else None,
            "avg_stop_hit_rate_pct": _round(sum(stop_rates) / len(stop_rates), 2) if stop_rates else None,
            "positive_folds": positive_folds,
            "negative_folds": negative_folds,
            "stable_positive_rate_pct": _rate(positive_folds, len(signal_rows)) if signal_rows else 0.0,
        }
        item["score"] = score_threshold_summary(item, requested_folds=requested_folds)
        item["quality_label"] = threshold_quality_label(item, requested_folds=requested_folds)
        summary.append(item)
    summary.sort(
        key=lambda row: (
            {"stable": 3, "promising": 2, "weak": 1, "unstable": 0}.get(str(row.get("quality_label")), 0),
            _to_float(row.get("score")) or -999,
            _to_float(row.get("avg_profit_factor")) or -999,
            _to_float(row.get("avg_trade_return_pct")) or -999,
        ),
        reverse=True,
    )
    return summary


def _recommendation(best: dict[str, Any] | None, *, folds_completed: int) -> str:
    if folds_completed <= 0:
        return "needs_more_data"
    if not best:
        return "reject"
    quality = best.get("quality_label")
    avg_return = _to_float(best.get("avg_trade_return_pct")) or 0.0
    avg_pf = _to_float(best.get("avg_profit_factor")) or 0.0
    total_signals = int(best.get("total_signals") or 0)
    if quality == "stable" and avg_pf >= 1.08 and avg_return > 0 and total_signals >= 50:
        return "use_as_research_gate"
    if quality in {"stable", "promising"} and avg_return > 0 and avg_pf >= 1.03:
        return "promising_but_unstable"
    return "reject"


def build_ml_v2_high_confidence_validation(
    db: Session,
    *,
    max_tickers: int = 120,
    max_samples: int = 10000,
    min_history: int = 80,
    horizon: int = 30,
    policy_id: str = "atr_t1_5_s1_6_h30_rr0_8",
    label: str = "positive_trade_return",
    folds: int = 4,
    train_ratio: float = 0.6,
    min_train_samples: int = 500,
    min_test_samples: int = 150,
    thresholds: list[float] | None = None,
    commission_bps: float = 10.0,
    slippage_bps: float = 5.0,
) -> dict[str, Any]:
    threshold_values = thresholds or DEFAULT_THRESHOLDS
    warnings: list[str] = []
    if label not in SUPPORTED_LABELS:
        return {
            "ok": False,
            "mode": "ml_v2_high_confidence_validation",
            "message": f"Unsupported label. Supported labels: {sorted(SUPPORTED_LABELS)}",
            "summary": {"folds_completed": 0},
            "threshold_summary": [],
            "folds": [],
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
            "mode": "ml_v2_high_confidence_validation",
            "summary": {
                "samples": 0,
                "tickers_used": 0,
                "folds_requested": folds,
                "folds_completed": 0,
                "recommendation": "needs_more_data",
                "warnings": warnings + ["Dataset has no samples."],
            },
            "threshold_summary": [],
            "folds": [],
            "best_threshold": None,
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
    ranges = _fold_ranges(len(X), folds, train_ratio, min_train_samples, min_test_samples)
    if not ranges:
        warnings.append("Not enough samples to create requested walk-forward folds.")
    fold_results: list[dict[str, Any]] = []
    feature_scores: dict[str, float] = {}

    for fold_index, (train_start, train_end, test_end) in enumerate(ranges, start=1):
        X_train, X_test = X[train_start:train_end], X[train_end:test_end]
        y_train, y_test = y[train_start:train_end], y[train_end:test_end]
        rows_test = rows[train_end:test_end]
        train_dates = dates[train_start:train_end]
        test_dates = dates[train_end:test_end]
        fold_warnings: list[str] = []
        if len(set(y_train)) < 2 or len(set(y_test)) < 2:
            fold_warnings.append("fold skipped: train or test split has only one class")
            fold_results.append(
                {
                    "fold": fold_index,
                    "train_period": _period(train_dates),
                    "test_period": _period(test_dates),
                    "train_positive_rate_pct": _rate(sum(y_train), len(y_train)),
                    "test_positive_rate_pct": _rate(sum(y_test), len(y_test)),
                    "auc": None,
                    "brier": None,
                    "threshold_report": [],
                    "warnings": fold_warnings,
                }
            )
            continue
        model, error = train_ml_v2_classifier(X_train, y_train)
        if model is None:
            fold_warnings.append(error or "fold skipped: model training failed")
            continue
        probabilities = predict_ml_v2_probabilities(model, X_test)
        for item in ml_v2_feature_importance(model, dataset.get("feature_names") or [])[:20]:
            feature = str(item.get("feature"))
            feature_scores[feature] = feature_scores.get(feature, 0.0) + (_to_float(item.get("importance")) or 0.0)
        report = build_ml_v2_threshold_report(rows_test, y_test, probabilities, thresholds=threshold_values)
        best_fold_threshold = max(
            report,
            key=lambda row: (
                _to_float(row.get("avg_trade_return_pct")) or -999,
                _to_float(row.get("profit_factor")) or -999,
                int(row.get("signals") or 0),
            ),
        ) if report else None
        fold_results.append(
            {
                "fold": fold_index,
                "train_period": _period(train_dates),
                "test_period": _period(test_dates),
                "train_positive_rate_pct": _rate(sum(y_train), len(y_train)),
                "test_positive_rate_pct": _rate(sum(y_test), len(y_test)),
                "auc": _safe_auc(y_test, probabilities),
                "brier": _brier(y_test, probabilities),
                "best_threshold_pct": (best_fold_threshold or {}).get("threshold_pct"),
                "threshold_report": report,
                "warnings": fold_warnings,
            }
        )

    completed_folds = [fold for fold in fold_results if fold.get("threshold_report")]
    threshold_summary = aggregate_threshold_summary(completed_folds, threshold_values)
    best = threshold_summary[0] if threshold_summary else None
    feature_importance = [
        {"feature": feature, "importance": _round(score / max(1, len(completed_folds)), 6)}
        for feature, score in feature_scores.items()
    ]
    feature_importance.sort(key=lambda row: float(row.get("importance") or 0.0), reverse=True)
    summary = {
        "samples": len(X),
        "tickers_used": (dataset.get("summary") or {}).get("tickers_used"),
        "folds_requested": folds,
        "folds_completed": len(completed_folds),
        "best_threshold_pct": (best or {}).get("threshold_pct"),
        "best_score": (best or {}).get("score"),
        "best_quality_label": (best or {}).get("quality_label"),
        "recommendation": _recommendation(best, folds_completed=len(completed_folds)),
        "warnings": warnings,
    }
    if len(completed_folds) < folds:
        summary["warnings"].append("Some folds were skipped or incomplete; inspect fold warnings.")
    return {
        "ok": True,
        "mode": "ml_v2_high_confidence_validation",
        "summary": summary,
        "threshold_summary": threshold_summary,
        "folds": fold_results,
        "best_threshold": best,
        "feature_importance": feature_importance[:20],
        "limitations": [
            "ML v2 high-confidence validation is a research layer and is not a production gate.",
            "Labels are proxy trade outcomes from daily candles and simplified costs.",
            "Daily candles do not provide full intraday target/stop sequence.",
            "High thresholds can have small sample risk.",
            "Promising thresholds still need paper trading validation.",
        ],
    }
