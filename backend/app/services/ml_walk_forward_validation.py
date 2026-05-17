from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.ml_probability_engine import (
    _apply_bin_calibration,
    _brier,
    _calibration_bins,
    _safe_auc,
)
from app.services.ml_probability_evaluation import _safe_precision
from app.services.ml_signal_dataset import build_ml_signal_dataset


def _threshold_report(
    y_true: list[int],
    probabilities: list[float],
    thresholds: list[float],
) -> list[dict[str, Any]]:
    rows = [_safe_precision(y_true, probabilities, threshold) for threshold in thresholds]

    for row in rows:
      row["coverage_pct"] = (
          round(int(row.get("signals") or 0) / len(y_true) * 100, 2)
          if y_true
          else 0.0
      )

    return rows


def _best_threshold(
    rows: list[dict[str, Any]],
    base_rate_pct: float | None,
    min_signals: int,
) -> dict[str, Any] | None:
    base = float(base_rate_pct or 0)

    candidates: list[dict[str, Any]] = []

    for row in rows:
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


def _make_folds(total: int, folds: int, test_fraction: float) -> list[tuple[int, int]]:
    test_size = max(100, int(total * test_fraction))
    start = max(0, total - test_size * folds)

    result: list[tuple[int, int]] = []

    for index in range(folds):
        test_start = start + index * test_size
        test_end = min(test_start + test_size, total)

        if test_end - test_start >= 50:
            result.append((test_start, test_end))

    return result


def validate_ml_walk_forward(
    db: Session,
    *,
    target_pct: float = 0.05,
    stop_pct: float = 0.03,
    horizon: int = 30,
    min_history: int = 60,
    max_tickers: int = 450,
    max_samples: int = 60_000,
    folds: int = 4,
    test_fraction: float = 0.12,
    thresholds: list[float] | None = None,
    min_train_samples: int = 3_000,
    min_signals: int = 30,
) -> dict[str, Any]:
    try:
        from sklearn.ensemble import GradientBoostingClassifier
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": f"ML dependencies are missing: {exc}",
        }

    threshold_values = thresholds or [0.25, 0.30, 0.35, 0.40, 0.45, 0.50]

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

    if len(X) < min_train_samples + 300:
        return {
            "ok": False,
            "error": "Not enough samples for walk-forward validation.",
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

    fold_ranges = _make_folds(total=len(X), folds=folds, test_fraction=test_fraction)

    fold_results: list[dict[str, Any]] = []

    for fold_index, (test_start, test_end) in enumerate(fold_ranges, start=1):
        if test_start < min_train_samples:
            continue

        calibration_start = max(int(test_start * 0.85), test_start - max(300, int(test_start * 0.15)))

        X_train = X[:calibration_start]
        y_train = y[:calibration_start]

        X_calibration = X[calibration_start:test_start]
        y_calibration = y[calibration_start:test_start]

        X_test = X[test_start:test_end]
        y_test = y[test_start:test_end]
        test_dates = dates[test_start:test_end]

        if len(X_train) < min_train_samples or len(X_calibration) < 100 or len(X_test) < 50:
            continue

        if len(set(y_train)) < 2 or len(set(y_test)) < 2:
            continue

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

        base_rate_pct = round(sum(y_test) / len(y_test) * 100, 2) if y_test else None
        threshold_rows = _threshold_report(y_test, test_calibrated, threshold_values)
        best = _best_threshold(threshold_rows, base_rate_pct, min_signals=min_signals)

        fold_results.append(
            {
                "fold": fold_index,
                "train_samples": len(y_train),
                "calibration_samples": len(y_calibration),
                "test_samples": len(y_test),
                "test_first_date": test_dates[0] if test_dates else None,
                "test_last_date": test_dates[-1] if test_dates else None,
                "test_positive_rate_pct": base_rate_pct,
                "raw_auc": _safe_auc(y_test, test_raw),
                "calibrated_auc": _safe_auc(y_test, test_calibrated),
                "raw_brier": _brier(y_test, test_raw),
                "calibrated_brier": _brier(y_test, test_calibrated),
                "best_threshold": best,
                "threshold_report": threshold_rows,
            }
        )

    ok_folds = [row for row in fold_results if row.get("calibrated_auc") is not None]

    if ok_folds:
        avg_auc = round(
            sum(float(row["calibrated_auc"]) for row in ok_folds) / len(ok_folds),
            4,
        )
        avg_brier = round(
            sum(float(row["calibrated_brier"]) for row in ok_folds if row.get("calibrated_brier") is not None) / len(ok_folds),
            4,
        )
        best_lifts = [
            float((row.get("best_threshold") or {}).get("lift_vs_base_pct"))
            for row in ok_folds
            if (row.get("best_threshold") or {}).get("lift_vs_base_pct") is not None
        ]
        avg_best_lift = round(sum(best_lifts) / len(best_lifts), 2) if best_lifts else None
        positive_lift_folds = sum(1 for value in best_lifts if value > 0)
    else:
        avg_auc = None
        avg_brier = None
        avg_best_lift = None
        positive_lift_folds = 0

    return {
        "ok": True,
        "config": {
            "target_pct": target_pct,
            "stop_pct": stop_pct,
            "horizon": horizon,
            "min_history": min_history,
            "max_tickers": max_tickers,
            "max_samples": max_samples,
            "folds": folds,
            "test_fraction": test_fraction,
            "thresholds": threshold_values,
            "min_signals": min_signals,
        },
        "dataset_summary": summary,
        "folds_count": len(fold_results),
        "summary": {
            "avg_calibrated_auc": avg_auc,
            "avg_calibrated_brier": avg_brier,
            "avg_best_lift_vs_base_pct": avg_best_lift,
            "positive_lift_folds": positive_lift_folds,
            "usable_folds": len(ok_folds),
        },
        "folds": fold_results,
        "interpretation": [
            "Если positive_lift_folds близко к usable_folds, ML стабильно добавляет ценность.",
            "Если lift есть только в одном fold, модель нельзя усиливать в consumer-сигналах.",
            "Смотрите не только AUC, но и best_threshold: он показывает практическую пользу отбора сигналов.",
        ],
    }
