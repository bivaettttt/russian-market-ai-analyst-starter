from __future__ import annotations

import threading
from typing import Any

from sqlalchemy.orm import Session

from app.services.adaptive_trade_calibration import aggregate_trade_pnl_metrics
from app.services.consumer_signals import _round, _to_float
from app.services.ml_probability_engine import _brier, _safe_auc
from app.services.ml_v2_dataset import build_ml_v2_trade_dataset


SUPPORTED_LABELS = {"positive_trade_return", "target_hit", "avoid_stop", "good_trade"}
THRESHOLDS = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]
_SKLEARN_LOCK = threading.Lock()


def _rate(part: int, total: int) -> float | None:
    return _round(part / total * 100, 2) if total else None


def build_ml_v2_threshold_report(
    rows: list[dict[str, Any]],
    y_true: list[int],
    probabilities: list[float],
    *,
    thresholds: list[float] | None = None,
) -> list[dict[str, Any]]:
    threshold_values = thresholds or THRESHOLDS
    report: list[dict[str, Any]] = []
    total = len(rows)
    for threshold in threshold_values:
        selected = [
            (row, label, probability)
            for row, label, probability in zip(rows, y_true, probabilities)
            if probability >= threshold
        ]
        selected_rows = [item[0] for item in selected]
        selected_labels = [item[1] for item in selected]
        selected_probs = [item[2] for item in selected]
        pnl = aggregate_trade_pnl_metrics(
            [{"outcome": row.get("outcome"), "trade_return_pct": row.get("trade_return_pct")} for row in selected_rows]
        )
        signals = len(selected)
        row = {
            "threshold_pct": _round(threshold * 100, 1),
            "signals": signals,
            "coverage_pct": _round(signals / total * 100, 2) if total else 0.0,
            "avg_probability_pct": _round(sum(selected_probs) / signals * 100, 2) if signals else None,
            "hit_rate_pct": _rate(sum(selected_labels), signals),
            "positive_rate_pct": _rate(sum(1 for item in selected_rows if (_to_float(item.get("trade_return_pct")) or 0.0) > 0), signals),
            "quality_label": "unstable" if signals < 30 else "ok",
            **pnl,
        }
        report.append(row)
    return report


def _feature_importance(model: Any, feature_names: list[str]) -> list[dict[str, Any]]:
    importances = getattr(model, "feature_importances_", None)
    if importances is None:
        coefficients = getattr(model, "coef_", None)
        if coefficients is not None and len(coefficients):
            importances = [abs(float(value)) for value in coefficients[0]]
    if importances is None:
        return []
    rows = [
        {"feature": feature, "importance": _round(float(importance), 6)}
        for feature, importance in zip(feature_names, importances)
    ]
    rows.sort(key=lambda item: float(item.get("importance") or 0.0), reverse=True)
    return rows[:30]


def _period(dates: list[str]) -> dict[str, Any]:
    return {
        "samples": len(dates),
        "first_date": dates[0] if dates else None,
        "last_date": dates[-1] if dates else None,
    }


def evaluate_ml_v2_trade_model(
    db: Session,
    *,
    max_tickers: int = 120,
    max_samples: int = 10000,
    min_history: int = 80,
    horizon: int = 30,
    policy_id: str = "atr_t1_5_s1_6_h30_rr0_8",
    label: str = "positive_trade_return",
    test_size: float = 0.25,
    commission_bps: float = 10.0,
    slippage_bps: float = 5.0,
) -> dict[str, Any]:
    warnings: list[str] = []
    if label not in SUPPORTED_LABELS:
        return {
            "ok": False,
            "mode": "ml_v2_trade_model_evaluation",
            "label": label,
            "message": f"Unsupported label. Supported labels: {sorted(SUPPORTED_LABELS)}",
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
            "ok": False,
            "mode": "ml_v2_trade_model_evaluation",
            "label": label,
            "message": "Could not build ML v2 dataset.",
            "dataset_summary": dataset.get("summary") or {},
            "warnings": warnings,
        }

    X = dataset["X"]
    y = dataset["labels"][label]
    rows = dataset["rows"]
    dates = dataset["dates"]
    order = sorted(range(len(X)), key=lambda index: dates[index])
    X = [X[index] for index in order]
    y = [int(y[index]) for index in order]
    rows = [rows[index] for index in order]
    dates = [dates[index] for index in order]

    split_index = int(len(X) * (1.0 - test_size))
    split_index = max(1, min(len(X) - 1, split_index))
    X_train, X_test = X[:split_index], X[split_index:]
    y_train, y_test = y[:split_index], y[split_index:]
    rows_test = rows[split_index:]
    train_dates, test_dates = dates[:split_index], dates[split_index:]

    if len(set(y_train)) < 2 or len(set(y_test)) < 2:
        return {
            "ok": False,
            "mode": "ml_v2_trade_model_evaluation",
            "label": label,
            "message": "Train or test split has only one class.",
            "dataset_summary": dataset.get("summary") or {},
            "train_period": _period(train_dates),
            "test_period": _period(test_dates),
            "warnings": warnings + ["Use more samples/tickers or another label."],
        }

    with _SKLEARN_LOCK:
        try:
            from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "mode": "ml_v2_trade_model_evaluation",
                "label": label,
                "message": f"ML dependencies are missing: {exc}",
            }
        try:
            model = RandomForestClassifier(
                random_state=42,
                n_estimators=180,
                max_depth=6,
                min_samples_leaf=20,
                n_jobs=1,
            )
            model.fit(X_train, y_train)
        except Exception:  # noqa: BLE001
            model = HistGradientBoostingClassifier(
                random_state=42,
                max_iter=160,
                learning_rate=0.04,
                max_leaf_nodes=24,
                l2_regularization=0.05,
            )
            model.fit(X_train, y_train)
        probabilities = [float(item[1]) for item in model.predict_proba(X_test)]
    threshold_report = build_ml_v2_threshold_report(rows_test, y_test, probabilities)
    test_pnl = aggregate_trade_pnl_metrics(
        [{"outcome": row.get("outcome"), "trade_return_pct": row.get("trade_return_pct")} for row in rows_test]
    )
    baseline_positive_rate = _rate(sum(y_test), len(y_test))
    metrics = {
        "auc": _safe_auc(y_test, probabilities),
        "brier": _brier(y_test, probabilities),
        "baseline_positive_rate_pct": baseline_positive_rate,
        "test_avg_trade_return_pct": test_pnl.get("avg_trade_return_pct"),
        "test_profit_factor": test_pnl.get("profit_factor"),
        "test_win_rate_pct": test_pnl.get("win_rate_pct"),
        "test_stop_hit_rate_pct": test_pnl.get("stop_hit_rate_pct"),
    }
    return {
        "ok": True,
        "mode": "ml_v2_trade_model_evaluation",
        "label": label,
        "dataset_summary": dataset.get("summary") or {},
        "train_period": _period(train_dates),
        "test_period": _period(test_dates),
        "metrics": metrics,
        "threshold_report": threshold_report,
        "feature_importance": _feature_importance(model, dataset.get("feature_names") or []),
        "warnings": warnings,
        "limitations": [
            "ML v2 is a research layer and is not used by production consumer signal logic.",
            "Labels are proxy trade outcomes from daily candles and simplified costs.",
            "Daily candles do not provide intraday target/stop order beyond conservative handling in simulation.",
            "Historical news/global context is not replayed as predictive features to avoid fake look-ahead.",
            "Time split reduces leakage but does not replace walk-forward validation.",
        ],
    }
