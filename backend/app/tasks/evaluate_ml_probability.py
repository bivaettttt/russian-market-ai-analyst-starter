from __future__ import annotations

import argparse
import asyncio
import json

from app.db import SessionLocal
from app.services.ml_probability_evaluation import evaluate_ml_probability_model


async def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ML probability model.")
    parser.add_argument(
        "--thresholds",
        default="0.30,0.35,0.40,0.45,0.50,0.55,0.60",
        help="Comma-separated probability thresholds, for example: 0.4,0.5,0.6",
    )
    parser.add_argument("--max-samples", type=int, default=None)

    args = parser.parse_args()

    thresholds = [
        float(item.strip())
        for item in args.thresholds.split(",")
        if item.strip()
    ]

    db = SessionLocal()
    try:
        result = evaluate_ml_probability_model(
            db=db,
            thresholds=thresholds,
            max_samples=args.max_samples,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
