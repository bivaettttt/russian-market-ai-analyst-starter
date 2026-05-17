from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.ml_probability_engine import (
    _apply_bin_calibration,
    _artifact_path,
    _brier,
    _safe_auc,
)
from app.services.ml_signal_dataset import build_ml_signal_dataset


def _safe_precision(
    y_true: list[int],
    probabilities: list[float],
    threshold: float,
) -> dict[str, Any]:
    selected = [
        (label, probability)
        for label, probability in zip(y_true, probabilities)
        if probability >= threshold
    ]

    if not selected:
        return {
            "threshold_pct": round(threshold * 100, 1),
            "signals": 0,
            "hit_rate_pct": None,
            "avg_probability_pct": None,
            "coverage_pct": 0.0,
            "successes": 0,
            "failures": 0,
        }

    labels = [item[0] for item in selected]
    probs = [item[1] for item in selected]
    successes = sum(labels)

    return {
        "threshold_pct": round(threshold * 100, 1),
        "signals": len(selected),
        "hit_rate_pct": round(successes / len(selected) * 100, 2),
        "avg_probability_pct": round(sum(probs) / len(probs) * 100, 2),
        "coverage_pct": None,
        "successes": successes,
        "failures": len(selected) - successes,
    }


def _calibration_report(
    y_true: list[int],
    probabilities: list[float],
    bins: int = 10,
) -> list[dict[str, Any]]:
    report: list[dict[str, Any]] = []

    for index in range(bins):
        low = index / bins
        high = (index + 1) / bins

        selected = [
            (label, probability)
            for label, probability in zip(y_true, probabilities)
            if low <= probability < high or (index == bins - 1 and probability == 1.0)
        ]

        if not selected:
            report.append(
                {
                    "bucket": f"{int(low * 100)}-{int(high * 100)}%",
                    "count": 0,
                    "avg_probability_pct": None,
                    "hit_rate_pct": None,
                    "calibration_error_pct": None,
                }
            )
            continue

        labels = [item[0] for item in selected]
        probs = [item[1] for item in selected]

        avg_probability = sum(probs) / len(probs)
        hit_rate = sum(labels) / len(labels)

        report.append(
            {
                "bucket": f"{int(low * 100)}-{int(high * 100)}%",
                "count": len(selected),
                "avg_probability_pct": round(avg_probability * 100, 2),
                "hit_rate_pct": round(hit_rate * 100, 2),
                "calibration_error_pct": round(abs(avg_probability - hit_rate) * 100, 2),
            }
        )

    return report


def _feature_importance(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    model = artifact.get("model")
    feature_names = artifact.get("feature_names") or []
    importances = getattr(model, "feature_importances_", None)

    if importances is None:
        return []

    rows = [
        {
            "feature": feature,
            "importance": round(float(importance), 6),
        }
        for feature, importance in zip(feature_names, importances)
    ]

    rows.sort(key=lambda item: item["importance"], reverse=True)
    return rows


def evaluate_ml_probability_model(
    db: Session,
    thresholds: list[float] | None = None,
    max_samples: int | None = None,
) -> dict[str, Any]:
    path = _artifact_path()

    if not path.exists():
        return {
            "ok": False,
            "trained": False,
            "message": "ML probability model is not trained yet.",
            "artifact_path": str(path),
        }

    try:
        import joblib
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "trained": False,
            "message": f"Cannot import joblib: {exc}",
        }

    artifact = joblib.load(path)
    metadata = artifact.get("metadata") or {}
    dataset_summary = metadata.get("dataset_summary") or {}

    target_pct = float(metadata.get("target_pct") or dataset_summary.get("target_pct") or 0.04)
    stop_pct = float(metadata.get("stop_pct") or dataset_summary.get("stop_pct") or 0.025)
    horizon = int(metadata.get("horizon") or dataset_summary.get("horizon") or 20)
    min_history = int(metadata.get("min_history") or dataset_summary.get("min_history") or 60)
    max_tickers = int(metadata.get("max_tickers") or 500)
    max_samples_value = int(max_samples or metadata.get("max_samples") or 60_000)

    dataset = build_ml_signal_dataset(
        db=db,
        target_pct=target_pct,
        stop_pct=stop_pct,
        horizon=horizon,
        min_history=min_history,
        max_tickers=max_tickers,
        max_samples=max_samples_value,
    )

    if not dataset.get("ok"):
        return {
            "ok": False,
            "trained": True,
            "message": "Could not rebuild evaluation dataset.",
            "dataset_summary": dataset.get("summary") or {},
        }

    X = dataset["X"]
    y = dataset["y"]
    dates = dataset["dates"]

    order = sorted(range(len(X)), key=lambda index: dates[index])
    X = [X[index] for index in order]
    y = [y[index] for index in order]
    dates = [dates[index] for index in order]

    calibration_end = int(len(X) * 0.85)

    X_test = X[calibration_end:]
    y_test = y[calibration_end:]
    test_dates = dates[calibration_end:]

    model = artifact["model"]
    calibration_table = artifact.get("calibration_table") or []

    raw_probabilities = [float(item[1]) for item in model.predict_proba(X_test)]
    calibrated_probabilities = [
        _apply_bin_calibration(value, calibration_table)
        for value in raw_probabilities
    ]

    threshold_values = thresholds or [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]

    threshold_report = [
        _safe_precision(y_test, calibrated_probabilities, threshold)
        for threshold in threshold_values
    ]

    for item in threshold_report:
        if y_test:
            item["coverage_pct"] = round(item["signals"] / len(y_test) * 100, 2)

    test_positive_rate = sum(y_test) / len(y_test) if y_test else 0.0

    return {
        "ok": True,
        "trained": True,
        "artifact_path": str(path),
        "metadata": metadata,
        "dataset_summary": dataset.get("summary") or {},
        "test_period": {
            "samples": len(y_test),
            "first_date": test_dates[0] if test_dates else None,
            "last_date": test_dates[-1] if test_dates else None,
            "positive_rate_pct": round(test_positive_rate * 100, 2) if y_test else None,
        },
        "metrics": {
            "raw_auc": _safe_auc(y_test, raw_probabilities),
            "calibrated_auc": _safe_auc(y_test, calibrated_probabilities),
            "raw_brier": _brier(y_test, raw_probabilities),
            "calibrated_brier": _brier(y_test, calibrated_probabilities),
        },
        "threshold_report": threshold_report,
        "calibration_report": _calibration_report(y_test, calibrated_probabilities),
        "feature_importance": _feature_importance(artifact),
        "interpretation": [
            "threshold_report показывает качество только тех сигналов, где ML probability выше порога.",
            "hit_rate_pct надо сравнивать с test_positive_rate_pct: если выше — модель добавляет ценность.",
            "coverage_pct показывает, какую долю test-сценариев модель готова отобрать на данном пороге.",
            "feature_importance помогает понять, какие признаки сейчас сильнее всего влияют на модель.",
        ],
    }
