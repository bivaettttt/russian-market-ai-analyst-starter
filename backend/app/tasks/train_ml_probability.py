from __future__ import annotations

import argparse
import asyncio
import json

from app.db import SessionLocal
from app.services.ml_probability_engine import train_ml_probability_model


async def main() -> None:
    parser = argparse.ArgumentParser(description="Train ML probability model for target-before-stop signals.")
    parser.add_argument("--target-pct", type=float, default=0.04)
    parser.add_argument("--stop-pct", type=float, default=0.025)
    parser.add_argument("--horizon", type=int, default=20)
    parser.add_argument("--min-history", type=int, default=60)
    parser.add_argument("--max-tickers", type=int, default=500)
    parser.add_argument("--max-samples", type=int, default=60000)

    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = train_ml_probability_model(
            db=db,
            target_pct=args.target_pct,
            stop_pct=args.stop_pct,
            horizon=args.horizon,
            min_history=args.min_history,
            max_tickers=args.max_tickers,
            max_samples=args.max_samples,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
