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


DEFAULT_SWEEP_CONFIGS: list[dict[str, Any]] = [
    {"target_pct": 0.02, "stop_pct": 0.02, "horizon": 10},
    {"target_pct": 0.03, "stop_pct": 0.02, "horizon": 15},
    {"target_pct": 0.04, "stop_pct": 0.025, "horizon": 20},
    {"target_pct": 0.05, "stop_pct": 0.03, "horizon": 30},
    {"target_pct": 0.06, "stop_pct": 0.035, "horizon": 40},
]


def _parse_config_item(raw: str) -> dict[str, Any]:
    parts = [item.strip() for item in raw.split(":") if item.strip()]

    if len(parts) != 3:
        raise ValueError(
            "Config must be target_pct:stop_pct:horizon, for example 0.03:0.02:15"
        )

    return {
        "target_pct": float(parts[0]),
        "stop_pct": float(parts[1]),
        "horizon": int(parts[2]),
    }


def parse_sweep_configs(raw: str | None) -> list[dict[str, Any]]:
    if not raw:
        return DEFAULT_SWEEP_CONFIGS

    return [_parse_config_item(item) for item in raw.split(",") if item.strip()]


def _best_threshold_row(
    threshold_report: list[dict[str, Any]],
    base_rate_pct: float | None,
    min_signals: int,
) -> dict[str, Any] | None:
    candidates = [
        row
        for row in threshold_report
        if row.get("hit_rate_pct") is not None
        and int(row.get("signals") or 0) >= min_signals
    ]

    if not candidates:
        return None

    base = float(base_rate_pct or 0)

    candidates.sort(
        key=lambda row: (
            float(row.get("hit_rate_pct") or 0) - base,
            float(row.get("hit_rate_pct") or 0),
            int(row.get("signals") or 0),
        ),
        reverse=True,
    )

    return candidates[0]


def _train_and_score_config(
    db: Session,
    config: dict[str, Any],
    *,
    min_history: int,
    max_tickers: int,
    max_samples: int,
    thresholds: list[float],
    min_signals: int,
) -> dict[str, Any]:
    try:
        from sklearn.ensemble import GradientBoostingClassifier
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "config": config,
            "error": f"ML dependencies are missing: {exc}",
        }

    dataset = build_ml_signal_dataset(
        db=db,
        target_pct=float(config["target_pct"]),
        stop_pct=float(config["stop_pct"]),
        horizon=int(config["horizon"]),
        min_history=min_history,
        max_tickers=max_tickers,
        max_samples=max_samples,
    )

    summary = dataset.get("summary") or {}

    if not dataset.get("ok") or int(summary.get("samples") or 0) < 500:
        return {
            "ok": False,
            "config": config,
            "error": "Not enough samples.",
            "dataset_summary": summary,
        }

    X = dataset["X"]
    y = dataset["y"]
    dates = dataset["dates"]

    if len(set(y)) < 2:
        return {
            "ok": False,
            "config": config,
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
    test_dates = dates[calibration_end:]

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

    threshold_report = [
        _safe_precision(y_test, test_calibrated, threshold)
        for threshold in thresholds
    ]

    for item in threshold_report:
        item["coverage_pct"] = (
            round(int(item.get("signals") or 0) / len(y_test) * 100, 2)
            if y_test
            else 0.0
        )
        item["lift_vs_base_pct"] = (
            round(float(item["hit_rate_pct"]) - float(base_rate_pct), 2)
            if item.get("hit_rate_pct") is not None and base_rate_pct is not None
            else None
        )

    best = _best_threshold_row(
        threshold_report=threshold_report,
        base_rate_pct=base_rate_pct,
        min_signals=min_signals,
    )

    return {
        "ok": True,
        "config": {
            "target_pct": float(config["target_pct"]),
            "stop_pct": float(config["stop_pct"]),
            "horizon": int(config["horizon"]),
        },
        "dataset_summary": summary,
        "split": {
            "train_samples": len(y_train),
            "calibration_samples": len(y_calibration),
            "test_samples": len(y_test),
            "test_first_date": test_dates[0] if test_dates else None,
            "test_last_date": test_dates[-1] if test_dates else None,
        },
        "metrics": {
            "test_positive_rate_pct": base_rate_pct,
            "raw_auc": _safe_auc(y_test, test_raw),
            "calibrated_auc": _safe_auc(y_test, test_calibrated),
            "raw_brier": _brier(y_test, test_raw),
            "calibrated_brier": _brier(y_test, test_calibrated),
        },
        "threshold_report": threshold_report,
        "best_threshold": best,
    }


def sweep_ml_targets(
    db: Session,
    *,
    configs: list[dict[str, Any]] | None = None,
    min_history: int = 60,
    max_tickers: int = 450,
    max_samples: int = 20_000,
    thresholds: list[float] | None = None,
    min_signals: int = 30,
) -> dict[str, Any]:
    threshold_values = thresholds or [0.25, 0.30, 0.35, 0.40, 0.45, 0.50]

    results = [
        _train_and_score_config(
            db=db,
            config=config,
            min_history=min_history,
            max_tickers=max_tickers,
            max_samples=max_samples,
            thresholds=threshold_values,
            min_signals=min_signals,
        )
        for config in (configs or DEFAULT_SWEEP_CONFIGS)
    ]

    ok_results = [row for row in results if row.get("ok")]

    summary_rows: list[dict[str, Any]] = []

    for row in ok_results:
        config = row["config"]
        metrics = row["metrics"]
        best = row.get("best_threshold") or {}

        summary_rows.append(
            {
                "target_pct": round(config["target_pct"] * 100, 2),
                "stop_pct": round(config["stop_pct"] * 100, 2),
                "horizon": config["horizon"],
                "samples": row.get("dataset_summary", {}).get("samples"),
                "test_samples": row.get("split", {}).get("test_samples"),
                "positive_rate_pct": metrics.get("test_positive_rate_pct"),
                "auc": metrics.get("calibrated_auc"),
                "brier": metrics.get("calibrated_brier"),
                "best_threshold_pct": best.get("threshold_pct"),
                "best_hit_rate_pct": best.get("hit_rate_pct"),
                "best_lift_vs_base_pct": best.get("lift_vs_base_pct"),
                "best_signals": best.get("signals"),
                "best_coverage_pct": best.get("coverage_pct"),
            }
        )

    summary_rows.sort(
        key=lambda item: (
            item.get("best_lift_vs_base_pct") is not None,
            item.get("best_lift_vs_base_pct") or -999,
            item.get("auc") or -999,
        ),
        reverse=True,
    )

    return {
        "ok": True,
        "configs_count": len(configs or DEFAULT_SWEEP_CONFIGS),
        "thresholds": threshold_values,
        "min_history": min_history,
        "max_tickers": max_tickers,
        "max_samples": max_samples,
        "min_signals": min_signals,
        "summary": summary_rows,
        "results": results,
        "interpretation": [
            "Выбирайте не максимальный AUC сам по себе, а постановку, где best_lift_vs_base_pct положительный и signals достаточно много.",
            "Если hit_rate не растёт при повышении threshold, ML нельзя использовать как buy engine.",
            "Если best_signals мало, постановка может быть статистически нестабильной.",
        ],
    }
