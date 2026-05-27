from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.db import SessionLocal
from app.services.adaptive_trade_calibration import aggregate_trade_pnl_metrics
from app.services.ml_probability_engine import _brier, _safe_auc
from app.services.ml_v2_evaluation import ml_v2_feature_importance, predict_ml_v2_probabilities, train_ml_v2_classifier
from app.services.ml_v3_consumer_candidate_dataset import (
    DEFAULT_POLICY_ID,
    FEATURE_SET_VERSION,
    build_ml_v3_consumer_candidate_dataset,
)
from app.services.ml_v3_consumer_candidate_evaluation import (
    SUPPORTED_LABELS,
    build_ml_v3_threshold_report,
)


MODEL_VERSION = "ml_v3_consumer_candidate_rf_v1"


def default_ml_v3_model_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "ml_v3_consumer_candidate_model.joblib"


def _period(dates: list[str]) -> dict[str, Any]:
    return {"samples": len(dates), "first_date": dates[0] if dates else None, "last_date": dates[-1] if dates else None}


def train_and_save_ml_v3_consumer_candidate_model(
    *,
    label: str = "positive_trade_return",
    max_tickers: int = 120,
    max_samples: int = 10000,
    min_history: int = 80,
    horizon: int = 30,
    policy_id: str = DEFAULT_POLICY_ID,
    test_size: float = 0.25,
    commission_bps: float = 10.0,
    slippage_bps: float = 5.0,
    include_watch_candidates: bool = False,
    output_path: str | None = None,
) -> dict[str, Any]:
    if label not in SUPPORTED_LABELS:
        return {"ok": False, "message": f"Unsupported label. Supported labels: {sorted(SUPPORTED_LABELS)}"}
    db = SessionLocal()
    try:
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
    finally:
        db.close()
    if not dataset.get("ok"):
        return {"ok": False, "message": "Could not build ML v3 consumer candidate dataset.", "dataset_summary": dataset.get("summary") or {}, "warnings": dataset.get("warnings") or []}

    X = dataset["X"]
    y = [int(value) for value in dataset["labels"][label]]
    rows = dataset["rows"]
    dates = [str(value or "") for value in dataset["dates"]]
    order = sorted(range(len(X)), key=lambda index: dates[index])
    X = [X[index] for index in order]
    y = [y[index] for index in order]
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
            "message": "Train or test split has only one class.",
            "dataset_summary": dataset.get("summary") or {},
            "train_period": _period(train_dates),
            "test_period": _period(test_dates),
            "warnings": (dataset.get("warnings") or []) + ["Use more samples/tickers or another label."],
        }
    model, error = train_ml_v2_classifier(X_train, y_train)
    if model is None:
        return {"ok": False, "message": error or "Could not train ML v3 classifier."}
    probabilities = predict_ml_v2_probabilities(model, X_test)
    threshold_report = build_ml_v3_threshold_report(rows_test, y_test, probabilities)
    test_pnl = aggregate_trade_pnl_metrics(
        [{"outcome": row.get("outcome"), "trade_return_pct": row.get("trade_return_pct")} for row in rows_test]
    )
    metrics = {
        "auc": _safe_auc(y_test, probabilities),
        "brier": _brier(y_test, probabilities),
        "test_avg_trade_return_pct": test_pnl.get("avg_trade_return_pct"),
        "test_profit_factor": test_pnl.get("profit_factor"),
        "test_win_rate_pct": test_pnl.get("win_rate_pct"),
        "test_stop_hit_rate_pct": test_pnl.get("stop_hit_rate_pct"),
    }
    metadata = {
        "model_version": MODEL_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "label": label,
        "policy_id": policy_id,
        "horizon": horizon,
        "feature_set": FEATURE_SET_VERSION,
        "dataset_summary": dataset.get("summary") or {},
        "train_period": _period(train_dates),
        "test_period": _period(test_dates),
        "metrics": metrics,
        "threshold_report": threshold_report,
    }
    artifact = {"model": model, "feature_names": dataset.get("feature_names") or [], "feature_set": FEATURE_SET_VERSION, "metadata": metadata}
    path = Path(output_path) if output_path else default_ml_v3_model_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    import joblib

    joblib.dump(artifact, path)
    return {
        "ok": True,
        "mode": "train_ml_v3_consumer_candidate",
        "artifact_path": str(path),
        "dataset_summary": dataset.get("summary") or {},
        "train_period": metadata["train_period"],
        "test_period": metadata["test_period"],
        "metrics": metrics,
        "threshold_report": threshold_report,
        "feature_importance": ml_v2_feature_importance(model, dataset.get("feature_names") or [])[:20],
        "warnings": dataset.get("warnings") or [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Train ML v3 consumer candidate research model artifact.")
    parser.add_argument("--label", default="positive_trade_return")
    parser.add_argument("--max-tickers", type=int, default=120)
    parser.add_argument("--max-samples", type=int, default=10000)
    parser.add_argument("--min-history", type=int, default=80)
    parser.add_argument("--horizon", type=int, default=30)
    parser.add_argument("--policy-id", default=DEFAULT_POLICY_ID)
    parser.add_argument("--test-size", type=float, default=0.25)
    parser.add_argument("--commission-bps", type=float, default=10.0)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    parser.add_argument("--include-watch-candidates", action="store_true")
    parser.add_argument("--output-path", default=None)
    args = parser.parse_args()
    result = train_and_save_ml_v3_consumer_candidate_model(
        label=args.label,
        max_tickers=args.max_tickers,
        max_samples=args.max_samples,
        min_history=args.min_history,
        horizon=args.horizon,
        policy_id=args.policy_id,
        test_size=args.test_size,
        commission_bps=args.commission_bps,
        slippage_bps=args.slippage_bps,
        include_watch_candidates=args.include_watch_candidates,
        output_path=args.output_path,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
