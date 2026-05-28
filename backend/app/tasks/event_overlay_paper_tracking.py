from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from app.db import SessionLocal
from app.services.event_overlay_paper_tracking import (
    build_event_overlay_paper_lifecycle_status,
    bulk_evaluate_ready_snapshots,
    create_conservative_overlay_paper_snapshot,
    run_conservative_overlay_daily_workflow,
)


def _print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Conservative event overlay paper tracking lifecycle")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="Show paper tracking lifecycle status")
    status_parser.add_argument("--as-of-date", default=None)

    create_parser = subparsers.add_parser("create", help="Create a conservative overlay paper snapshot")
    create_parser.add_argument("--name", default=None)
    create_parser.add_argument("--limit", type=int, default=100)
    create_parser.add_argument("--candles-limit", type=int, default=240)
    create_parser.add_argument("--horizon-days", type=int, default=20)
    create_parser.add_argument("--overlay-mode", default="soft_adjust")
    create_parser.add_argument("--no-dedupe", action="store_true")

    eval_parser = subparsers.add_parser("evaluate-ready", help="Evaluate ready paper snapshots")
    eval_parser.add_argument("--as-of-date", default=None)
    eval_parser.add_argument("--limit", type=int, default=50)

    daily_parser = subparsers.add_parser("daily-run", help="Create today's snapshot if needed and evaluate ready snapshots")
    daily_parser.add_argument("--name", default="daily")
    daily_parser.add_argument("--limit", type=int, default=100)
    daily_parser.add_argument("--candles-limit", type=int, default=240)
    daily_parser.add_argument("--horizon-days", type=int, default=20)
    daily_parser.add_argument("--overlay-mode", default="soft_adjust")
    daily_parser.add_argument("--evaluate-ready", action="store_true")
    daily_parser.add_argument("--no-evaluate-ready", action="store_true")
    daily_parser.add_argument("--dedupe-same-day", action="store_true")
    daily_parser.add_argument("--no-dedupe-same-day", action="store_true")

    args = parser.parse_args(argv)
    db = SessionLocal()
    try:
        if args.command == "status":
            result = build_event_overlay_paper_lifecycle_status(
                db,
                as_of_date=args.as_of_date,
            )
        elif args.command == "create":
            result = create_conservative_overlay_paper_snapshot(
                db,
                name=args.name,
                limit=args.limit,
                candles_limit=args.candles_limit,
                horizon_days=args.horizon_days,
                overlay_mode=args.overlay_mode,
                dedupe_same_day=not args.no_dedupe,
            )
        elif args.command == "evaluate-ready":
            result = bulk_evaluate_ready_snapshots(
                db,
                as_of_date=args.as_of_date,
                limit=args.limit,
            )
        elif args.command == "daily-run":
            should_evaluate = True
            if args.no_evaluate_ready:
                should_evaluate = False
            elif args.evaluate_ready:
                should_evaluate = True
            dedupe = True
            if args.no_dedupe_same_day:
                dedupe = False
            elif args.dedupe_same_day:
                dedupe = True
            result = run_conservative_overlay_daily_workflow(
                db,
                name=args.name,
                limit=args.limit,
                candles_limit=args.candles_limit,
                horizon_days=args.horizon_days,
                overlay_mode=args.overlay_mode,
                evaluate_ready=should_evaluate,
                dedupe_same_day=dedupe,
            )
        else:
            parser.error("unknown command")
            return 2
        _print_json(result)
        return 0 if result.get("ok") else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
