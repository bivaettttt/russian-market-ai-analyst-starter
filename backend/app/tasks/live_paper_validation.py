from __future__ import annotations

import argparse
import json
from typing import Any

from app.db import SessionLocal
from app.services.live_paper_validation_start import build_live_paper_validation_status, start_live_paper_validation_run


def _print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def _print_compact(data: dict[str, Any]) -> None:
    summary = data.get("summary") or {}
    print(f"ok={data.get('ok')} mode={data.get('mode')} status={data.get('status')}")
    for key, value in summary.items():
        print(f"{key}={value}")
    if data.get("blocked_reason"):
        print(f"blocked_reason={data.get('blocked_reason')}")
    if data.get("snapshot_id"):
        print(f"snapshot_id={data.get('snapshot_id')}")
    if data.get("warnings"):
        print("warnings=" + ",".join(data.get("warnings") or []))
    if data.get("next_steps"):
        print("next_steps=" + ",".join(data.get("next_steps") or []))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start official conservative overlay live paper validation")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="Show live paper validation readiness")
    status_parser.add_argument("--max-stale-days", type=int, default=3)
    status_parser.add_argument("--json", action="store_true")

    start_parser = subparsers.add_parser("start", help="Start official live paper validation run")
    start_parser.add_argument("--name", default="official-daily")
    start_parser.add_argument("--limit", type=int, default=100)
    start_parser.add_argument("--horizon-days", type=int, default=20)
    start_parser.add_argument("--refresh-max-tickers", type=int, default=150)
    start_parser.add_argument("--refresh-days", type=int, default=120)
    start_parser.add_argument("--dry-run", action="store_true")
    start_parser.add_argument("--no-refresh", action="store_true")
    start_parser.add_argument("--allow-stale", action="store_true")
    start_parser.add_argument("--no-evaluate-ready", action="store_true")
    start_parser.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    db = SessionLocal()
    try:
        if args.command == "status":
            result = build_live_paper_validation_status(db, max_stale_days=args.max_stale_days)
            full_json = args.json
        elif args.command == "start":
            result = start_live_paper_validation_run(
                db,
                name=args.name,
                limit=args.limit,
                horizon_days=args.horizon_days,
                refresh_market_data=not args.no_refresh,
                refresh_max_tickers=args.refresh_max_tickers,
                refresh_days=args.refresh_days,
                require_fresh_market_data=not args.allow_stale,
                evaluate_ready=not args.no_evaluate_ready,
                dry_run=args.dry_run,
            )
            full_json = args.json
        else:
            parser.error("unknown command")
            return 2
        _print_json(result) if full_json else _print_compact(result)
        if result.get("status") == "blocked":
            return 1
        return 0 if result.get("ok") else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
