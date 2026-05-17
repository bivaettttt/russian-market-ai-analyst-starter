from __future__ import annotations

import argparse
import asyncio
import json

from app.db import SessionLocal
from app.services.ml_walk_forward_validation import validate_ml_walk_forward


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run walk-forward validation for ML probability model.")
    parser.add_argument("--target-pct", type=float, default=0.05)
    parser.add_argument("--stop-pct", type=float, default=0.03)
    parser.add_argument("--horizon", type=int, default=30)
    parser.add_argument("--min-history", type=int, default=60)
    parser.add_argument("--max-tickers", type=int, default=450)
    parser.add_argument("--max-samples", type=int, default=60000)
    parser.add_argument("--folds", type=int, default=4)
    parser.add_argument("--test-fraction", type=float, default=0.12)
    parser.add_argument("--thresholds", default="0.25,0.30,0.35,0.40,0.45,0.50")
    parser.add_argument("--min-train-samples", type=int, default=3000)
    parser.add_argument("--min-signals", type=int, default=30)
    parser.add_argument("--summary-only", action="store_true")

    args = parser.parse_args()

    thresholds = [
        float(item.strip())
        for item in args.thresholds.split(",")
        if item.strip()
    ]

    db = SessionLocal()

    try:
        result = validate_ml_walk_forward(
            db=db,
            target_pct=args.target_pct,
            stop_pct=args.stop_pct,
            horizon=args.horizon,
            min_history=args.min_history,
            max_tickers=args.max_tickers,
            max_samples=args.max_samples,
            folds=args.folds,
            test_fraction=args.test_fraction,
            thresholds=thresholds,
            min_train_samples=args.min_train_samples,
            min_signals=args.min_signals,
        )

        if args.summary_only:
            print(json.dumps(
                {
                    "ok": result.get("ok"),
                    "config": result.get("config"),
                    "dataset_summary": result.get("dataset_summary"),
                    "summary": result.get("summary"),
                    "folds": [
                        {
                            "fold": row.get("fold"),
                            "test_first_date": row.get("test_first_date"),
                            "test_last_date": row.get("test_last_date"),
                            "test_positive_rate_pct": row.get("test_positive_rate_pct"),
                            "calibrated_auc": row.get("calibrated_auc"),
                            "calibrated_brier": row.get("calibrated_brier"),
                            "best_threshold": row.get("best_threshold"),
                        }
                        for row in result.get("folds") or []
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ))
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
