from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.ml_probability_engine import (
    _apply_bin_calibration,
    _brier,
    _calibration_bins,
    _safe_auc,
)
from app.services.ml_signal_dataset import build_ml_signal_dataset


DEFAULT_REGIME_FEATURES = [
    "volatility_20_pct",
    "atr_20_pct",
    "liquidity_log_value_20",
    "range_position_60_pct",
    "dist_low_60_pct",
    "dist_high_60_pct",
    "ma_50_gap_pct",
    "ret_20",
    "value_ratio_20",
]


def _percent(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(float(value) * 100, digits)


def _quantiles(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0

    ordered = sorted(values)
    q33 = ordered[int((len(ordered) - 1) * 0.33)]
    q66 = ordered[int((len(ordered) - 1) * 0.66)]

    return q33, q66


def _bucket_name(value: float, q33: float, q66: float) -> str:
    if value <= q33:
        return "low"
    if value <= q66:
        return "medium"
    return "high"


def _safe_rate(successes: int, total: int) -> float | None:
    if total <= 0:
        return None
    return round(successes / total * 100, 2)


def _regime_rows_for_feature(
    *,
    feature: str,
    values: list[float],
    y_true: list[int],
    probabilities: list[float],
    threshold: float,
    global_base_rate_pct: float | None,
    min_samples: int,
) -> list[dict[str, Any]]:
    q33, q66 = _quantiles(values)

    grouped: dict[str, list[int]] = {
        "low": [],
        "medium": [],
        "high": [],
    }

    for index, value in enumerate(values):
        grouped[_bucket_name(value, q33, q66)].append(index)

    rows: list[dict[str, Any]] = []

    for bucket, indices in grouped.items():
        samples = len(indices)

        if samples < min_samples:
            continue

        positives = sum(y_true[index] for index in indices)
        base_rate_pct = _safe_rate(positives, samples)

        selected_indices = [
            index
            for index in indices
            if probabilities[index] >= threshold
        ]

        selected_signals = len(selected_indices)
        selected_successes = sum(y_true[index] for index in selected_indices)

        hit_rate_pct = _safe_rate(selected_successes, selected_signals)

        lift_vs_bucket_base_pct = (
            round(hit_rate_pct - base_rate_pct, 2)
            if hit_rate_pct is not None and base_rate_pct is not None
            else None
        )

        lift_vs_global_base_pct = (
            round(hit_rate_pct - global_base_rate_pct, 2)
            if hit_rate_pct is not None and global_base_rate_pct is not None
            else None
        )

        bucket_values = [values[index] for index in indices]
        selected_probs = [probabilities[index] for index in selected_indices]

        rows.append(
            {
                "feature": feature,
                "bucket": bucket,
                "samples": samples,
                "bucket_min": round(min(bucket_values), 6),
                "bucket_max": round(max(bucket_values), 6),
                "base_rate_pct": base_rate_pct,
                "threshold_pct": round(threshold * 100, 2),
                "selected_signals": selected_signals,
                "selected_coverage_pct": round(selected_signals / samples * 100, 2),
                "selected_successes": selected_successes,
                "hit_rate_pct": hit_rate_pct,
                "lift_vs_bucket_base_pct": lift_vs_bucket_base_pct,
                "lift_vs_global_base_pct": lift_vs_global_base_pct,
                "avg_probability_pct": (
                    round(sum(selected_probs) / len(selected_probs) * 100, 2)
                    if selected_probs
                    else None
                ),
            }
        )

    rows.sort(
        key=lambda row: (
            row.get("lift_vs_bucket_base_pct") is not None,
            row.get("lift_vs_bucket_base_pct") or -999,
            row.get("selected_signals") or 0,
        ),
        reverse=True,
    )

    return rows


def evaluate_ml_regimes(
    db: Session,
    *,
    target_pct: float = 0.05,
    stop_pct: float = 0.03,
    horizon: int = 30,
    threshold: float = 0.35,
    min_history: int = 60,
    max_tickers: int = 450,
    max_samples: int = 60_000,
    features: list[str] | None = None,
    min_samples: int = 80,
) -> dict[str, Any]:
    try:
        from sklearn.ensemble import GradientBoostingClassifier
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": f"ML dependencies are missing: {exc}",
        }

    dataset = build_ml_signal_dataset(
        db=db,
        target_pct=target_pct,
        stop_pct=stop_pct,
        horizon=horizon,
        min_history=min_history,
        max_tickers=max_tickers,
        max_samples=max_samples,
    )

    summary = dataset.get("summary") or {}

    if not dataset.get("ok"):
        return {
            "ok": False,
            "error": "Could not build ML dataset.",
            "dataset_summary": summary,
        }

    X = dataset["X"]
    y = dataset["y"]
    dates = dataset["dates"]
    tickers = dataset.get("tickers") or []
    feature_names = dataset.get("feature_names") or []

    if len(X) < 1000:
        return {
            "ok": False,
            "error": "Not enough samples for regime evaluation.",
            "dataset_summary": summary,
            "samples": len(X),
        }

    if len(set(y)) < 2:
        return {
            "ok": False,
            "error": "Dataset has only one class.",
            "dataset_summary": summary,
        }

    order = sorted(range(len(X)), key=lambda index: dates[index])
    X = [X[index] for index in order]
    y = [y[index] for index in order]
    dates = [dates[index] for index in order]
    tickers = [tickers[index] for index in order] if tickers else []

    train_end = int(len(X) * 0.70)
    calibration_end = int(len(X) * 0.85)

    X_train = X[:train_end]
    y_train = y[:train_end]

    X_calibration = X[train_end:calibration_end]
    y_calibration = y[train_end:calibration_end]

    X_test = X[calibration_end:]
    y_test = y[calibration_end:]
    test_dates = dates[calibration_end:]
    test_tickers = tickers[calibration_end:] if tickers else []

    model = GradientBoostingClassifier(
        random_state=42,
        n_estimators=220,
        learning_rate=0.025,
        max_depth=3,
        subsample=0.85,
    )

    model.fit(X_train, y_train)

    calibration_raw = [float(item[1]) for item in model.predict_proba(X_calibration)]
    calibration_table = _calibration_bins(y_calibration, calibration_raw)

    test_raw = [float(item[1]) for item in model.predict_proba(X_test)]
    test_calibrated = [
        _apply_bin_calibration(value, calibration_table)
        for value in test_raw
    ]

    global_base_rate_pct = _safe_rate(sum(y_test), len(y_test))

    selected_features = features or DEFAULT_REGIME_FEATURES
    feature_index = {name: index for index, name in enumerate(feature_names)}

    missing_features = [
        feature
        for feature in selected_features
        if feature not in feature_index
    ]

    available_features = [
        feature
        for feature in selected_features
        if feature in feature_index
    ]

    regimes_by_feature: dict[str, list[dict[str, Any]]] = {}
    all_rows: list[dict[str, Any]] = []

    for feature in available_features:
        index = feature_index[feature]
        values = [float(row[index]) for row in X_test]

        rows = _regime_rows_for_feature(
            feature=feature,
            values=values,
            y_true=y_test,
            probabilities=test_calibrated,
            threshold=threshold,
            global_base_rate_pct=global_base_rate_pct,
            min_samples=min_samples,
        )

        regimes_by_feature[feature] = rows
        all_rows.extend(rows)

    positive_regimes = [
        row
        for row in all_rows
        if row.get("lift_vs_bucket_base_pct") is not None
        and row.get("lift_vs_bucket_base_pct") > 0
        and int(row.get("selected_signals") or 0) >= 20
    ]

    weak_regimes = [
        row
        for row in all_rows
        if row.get("lift_vs_bucket_base_pct") is not None
        and row.get("lift_vs_bucket_base_pct") < 0
        and int(row.get("selected_signals") or 0) >= 20
    ]

    positive_regimes.sort(
        key=lambda row: (
            row.get("lift_vs_bucket_base_pct") or -999,
            row.get("selected_signals") or 0,
        ),
        reverse=True,
    )

    weak_regimes.sort(
        key=lambda row: (
            row.get("lift_vs_bucket_base_pct") or 999,
            -(row.get("selected_signals") or 0),
        )
    )

    return {
        "ok": True,
        "config": {
            "target_pct": target_pct,
            "stop_pct": stop_pct,
            "horizon": horizon,
            "threshold": threshold,
            "threshold_pct": round(threshold * 100, 2),
            "min_history": min_history,
            "max_tickers": max_tickers,
            "max_samples": max_samples,
            "min_samples": min_samples,
            "features": selected_features,
        },
        "dataset_summary": summary,
        "split": {
            "train_samples": len(y_train),
            "calibration_samples": len(y_calibration),
            "test_samples": len(y_test),
            "test_first_date": test_dates[0] if test_dates else None,
            "test_last_date": test_dates[-1] if test_dates else None,
            "test_unique_tickers": len(set(test_tickers)) if test_tickers else None,
        },
        "metrics": {
            "test_positive_rate_pct": global_base_rate_pct,
            "raw_auc": _safe_auc(y_test, test_raw),
            "calibrated_auc": _safe_auc(y_test, test_calibrated),
            "raw_brier": _brier(y_test, test_raw),
            "calibrated_brier": _brier(y_test, test_calibrated),
        },
        "missing_features": missing_features,
        "regimes_by_feature": regimes_by_feature,
        "top_positive_regimes": positive_regimes[:12],
        "weak_regimes": weak_regimes[:12],
        "interpretation": [
            "Положительный lift внутри bucket означает, что ML лучше base rate именно в этом режиме.",
            "Отрицательный lift означает, что в этом режиме ML лучше использовать только как слабый сигнал или риск-фильтр.",
            "Regime report нужен для будущей адаптивной настройки веса ML.",
        ],
    }
