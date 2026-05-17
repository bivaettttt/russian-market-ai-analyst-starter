from __future__ import annotations

import argparse
import asyncio
import json

from app.db import SessionLocal
from app.services.ml_regime_evaluation import evaluate_ml_regimes


async def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ML quality by market regimes.")
    parser.add_argument("--target-pct", type=float, default=0.05)
    parser.add_argument("--stop-pct", type=float, default=0.03)
    parser.add_argument("--horizon", type=int, default=30)
    parser.add_argument("--threshold", type=float, default=0.35)
    parser.add_argument("--min-history", type=int, default=60)
    parser.add_argument("--max-tickers", type=int, default=450)
    parser.add_argument("--max-samples", type=int, default=60000)
    parser.add_argument("--min-samples", type=int, default=80)
    parser.add_argument("--features", default=None)
    parser.add_argument("--summary-only", action="store_true")

    args = parser.parse_args()

    features = [
        item.strip()
        for item in args.features.split(",")
        if item.strip()
    ] if args.features else None

    db = SessionLocal()

    try:
        result = evaluate_ml_regimes(
            db=db,
            target_pct=args.target_pct,
            stop_pct=args.stop_pct,
            horizon=args.horizon,
            threshold=args.threshold,
            min_history=args.min_history,
            max_tickers=args.max_tickers,
            max_samples=args.max_samples,
            min_samples=args.min_samples,
            features=features,
        )

        if args.summary_only:
            print(json.dumps(
                {
                    "ok": result.get("ok"),
                    "config": result.get("config"),
                    "dataset_summary": result.get("dataset_summary"),
                    "split": result.get("split"),
                    "metrics": result.get("metrics"),
                    "top_positive_regimes": result.get("top_positive_regimes"),
                    "weak_regimes": result.get("weak_regimes"),
                    "missing_features": result.get("missing_features"),
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
