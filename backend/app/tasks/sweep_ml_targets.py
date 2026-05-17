from __future__ import annotations

import argparse
import asyncio
import json

from app.db import SessionLocal
from app.services.ml_target_sweep import parse_sweep_configs, sweep_ml_targets


async def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep ML target/stop/horizon definitions.")
    parser.add_argument(
        "--configs",
        default=None,
        help=(
            "Comma-separated configs target_pct:stop_pct:horizon. "
            "Example: 0.02:0.02:10,0.03:0.02:15,0.04:0.025:20"
        ),
    )
    parser.add_argument(
        "--thresholds",
        default="0.25,0.30,0.35,0.40,0.45,0.50",
        help="Comma-separated probability thresholds.",
    )
    parser.add_argument("--min-history", type=int, default=60)
    parser.add_argument("--max-tickers", type=int, default=450)
    parser.add_argument("--max-samples", type=int, default=20_000)
    parser.add_argument("--min-signals", type=int, default=30)
    parser.add_argument("--summary-only", action="store_true")

    args = parser.parse_args()

    thresholds = [
        float(item.strip())
        for item in args.thresholds.split(",")
        if item.strip()
    ]

    configs = parse_sweep_configs(args.configs)

    db = SessionLocal()

    try:
        result = sweep_ml_targets(
            db=db,
            configs=configs,
            min_history=args.min_history,
            max_tickers=args.max_tickers,
            max_samples=args.max_samples,
            thresholds=thresholds,
            min_signals=args.min_signals,
        )

        if args.summary_only:
            print(json.dumps(
                {
                    "ok": result.get("ok"),
                    "thresholds": result.get("thresholds"),
                    "min_signals": result.get("min_signals"),
                    "summary": result.get("summary"),
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
