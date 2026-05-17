from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.services.ml_signal_dataset import build_latest_feature_vector, build_ml_signal_dataset


def _artifact_path() -> Path:
    backend_dir = Path(__file__).resolve().parents[2]
    data_dir = backend_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "ml_probability_model.joblib"


def _safe_auc(y_true: list[int], probabilities: list[float]) -> float | None:
    try:
        from sklearn.metrics import roc_auc_score

        if len(set(y_true)) < 2:
            return None

        return round(float(roc_auc_score(y_true, probabilities)), 4)
    except Exception:
        return None


def _brier(y_true: list[int], probabilities: list[float]) -> float | None:
    try:
        from sklearn.metrics import brier_score_loss

        return round(float(brier_score_loss(y_true, probabilities)), 4)
    except Exception:
        return None


def _calibration_bins(y_true: list[int], probabilities: list[float], bins: int = 10) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    for index in range(bins):
        low = index / bins
        high = (index + 1) / bins
        selected = [
            (label, prob)
            for label, prob in zip(y_true, probabilities)
            if low <= prob < high or (index == bins - 1 and prob == 1.0)
        ]

        if not selected:
            result.append(
                {
                    "low": low,
                    "high": high,
                    "count": 0,
                    "raw_avg": None,
                    "success_rate": None,
                }
            )
            continue

        labels = [item[0] for item in selected]
        probs = [item[1] for item in selected]

        result.append(
            {
                "low": low,
                "high": high,
                "count": len(selected),
                "raw_avg": round(sum(probs) / len(probs), 4),
                "success_rate": round(sum(labels) / len(labels), 4),
            }
        )

    return result


def _apply_bin_calibration(raw_probability: float, bins: list[dict[str, Any]]) -> float:
    for item in bins:
        low = float(item.get("low") or 0)
        high = float(item.get("high") or 1)
        count = int(item.get("count") or 0)
        success_rate = item.get("success_rate")

        if low <= raw_probability < high or (high == 1 and raw_probability == 1.0):
            if count >= 30 and success_rate is not None:
                return float(success_rate) * 0.65 + raw_probability * 0.35
            return raw_probability

    return raw_probability


def get_ml_probability_status() -> dict[str, Any]:
    path = _artifact_path()

    if not path.exists():
        return {
            "ok": False,
            "trained": False,
            "artifact_path": str(path),
            "message": "ML probability model is not trained yet.",
        }

    try:
        import joblib

        artifact = joblib.load(path)
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "trained": False,
            "artifact_path": str(path),
            "message": f"Cannot load ML artifact: {exc}",
        }

    metadata = artifact.get("metadata") or {}

    return {
        "ok": True,
        "trained": True,
        "artifact_path": str(path),
        "metadata": metadata,
        "metrics": artifact.get("metrics") or {},
        "feature_names": artifact.get("feature_names") or [],
    }


def train_ml_probability_model(
    db: Session,
    target_pct: float = 0.04,
    stop_pct: float = 0.025,
    horizon: int = 20,
    min_history: int = 60,
    max_tickers: int = 500,
    max_samples: int = 60_000,
) -> dict[str, Any]:
    try:
        import joblib
        from sklearn.ensemble import GradientBoostingClassifier
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": f"ML dependencies are missing: {exc}",
            "hint": "Run: cd backend && pip install -r requirements.txt",
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

    if not dataset.get("ok") or summary.get("samples", 0) < 500:
        return {
            "ok": False,
            "error": "Not enough ML samples.",
            "dataset_summary": summary,
        }

    X = dataset["X"]
    y = dataset["y"]
    dates = dataset["dates"]

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

    train_end = int(len(X) * 0.70)
    calibration_end = int(len(X) * 0.85)

    X_train = X[:train_end]
    y_train = y[:train_end]

    X_calibration = X[train_end:calibration_end]
    y_calibration = y[train_end:calibration_end]

    X_test = X[calibration_end:]
    y_test = y[calibration_end:]

    model = GradientBoostingClassifier(
        random_state=42,
        n_estimators=220,
        learning_rate=0.025,
        max_depth=3,
        subsample=0.85,
    )
    model.fit(X_train, y_train)

    calibration_probabilities = [float(item[1]) for item in model.predict_proba(X_calibration)]
    calibration_table = _calibration_bins(y_calibration, calibration_probabilities)

    test_raw = [float(item[1]) for item in model.predict_proba(X_test)]
    test_calibrated = [_apply_bin_calibration(value, calibration_table) for value in test_raw]

    metrics = {
        "test_samples": len(y_test),
        "test_positive_rate_pct": round(sum(y_test) / len(y_test) * 100, 2) if y_test else None,
        "raw_auc": _safe_auc(y_test, test_raw),
        "calibrated_auc": _safe_auc(y_test, test_calibrated),
        "raw_brier": _brier(y_test, test_raw),
        "calibrated_brier": _brier(y_test, test_calibrated),
    }

    artifact = {
        "model": model,
        "feature_names": dataset["feature_names"],
        "calibration_table": calibration_table,
        "metrics": metrics,
        "metadata": {
            "trained_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "target_pct": target_pct,
            "stop_pct": stop_pct,
            "horizon": horizon,
            "min_history": min_history,
            "max_tickers": max_tickers,
            "max_samples": max_samples,
            "dataset_summary": summary,
            "feature_set": dataset.get("feature_set"),
            "feature_count": len(dataset.get("feature_names") or []),
            "train_samples": len(y_train),
            "calibration_samples": len(y_calibration),
            "test_samples": len(y_test),
            "date_range": {
                "first": dates[0] if dates else None,
                "last": dates[-1] if dates else None,
                "test_start": dates[calibration_end] if len(dates) > calibration_end else None,
            },
        },
    }

    path = _artifact_path()
    joblib.dump(artifact, path)

    return {
        "ok": True,
        "artifact_path": str(path),
        "dataset_summary": summary,
        "metrics": metrics,
        "calibration_table": calibration_table,
        "metadata": artifact["metadata"],
    }


def predict_ml_probability_for_ticker(
    db: Session,
    ticker: str,
    min_history: int = 60,
) -> dict[str, Any]:
    try:
        import joblib
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "reason": "missing_dependency",
            "message": str(exc),
        }

    path = _artifact_path()

    if not path.exists():
        return {
            "ok": False,
            "reason": "model_not_trained",
            "message": "ML probability model is not trained yet.",
        }

    feature_result = build_latest_feature_vector(db=db, ticker=ticker, min_history=min_history)
    if not feature_result.get("ok"):
        return {
            "ok": False,
            "reason": feature_result.get("reason"),
            "message": "Cannot build latest feature vector.",
            "details": feature_result,
        }

    artifact = joblib.load(path)
    model = artifact["model"]
    calibration_table = artifact.get("calibration_table") or []

    artifact_features = artifact.get("feature_names") or []
    current_features = feature_result.get("feature_names") or []
    expected_count = len(artifact_features) or getattr(model, "n_features_in_", None)
    actual_count = len(feature_result.get("features") or [])

    if expected_count and actual_count != expected_count:
        return {
            "ok": False,
            "reason": "feature_mismatch",
            "message": (
                f"ML artifact expects {expected_count} features, "
                f"but current feature builder produced {actual_count}. Retrain the model."
            ),
            "artifact_feature_count": expected_count,
            "current_feature_count": actual_count,
            "artifact_feature_names": artifact_features,
            "current_feature_names": current_features,
        }

    raw_probability = float(model.predict_proba([feature_result["features"]])[0][1])
    calibrated_probability = _apply_bin_calibration(raw_probability, calibration_table)

    return {
        "ok": True,
        "ticker": ticker.upper().strip(),
        "trade_date": feature_result.get("trade_date"),
        "raw_probability_pct": round(raw_probability * 100, 1),
        "ml_probability_pct": round(calibrated_probability * 100, 1),
        "feature_names": feature_result.get("feature_names"),
        "features": feature_result.get("features"),
        "metadata": artifact.get("metadata") or {},
        "metrics": artifact.get("metrics") or {},
    }
