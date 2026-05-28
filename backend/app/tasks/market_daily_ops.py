from __future__ import annotations

import argparse
import json
from typing import Any

from app.db import SessionLocal
from app.services.market_daily_ops import build_daily_ops_status, run_market_daily_ops
from app.services.market_data_refresh import refresh_market_data_daily


def _print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def _print_compact(data: dict[str, Any]) -> None:
    summary = data.get("summary") or {}
    print(f"ok={data.get('ok')} mode={data.get('mode')}")
    for key in [
        "latest_candle_date",
        "market_data_stale",
        "market_refresh_status",
        "created_snapshot",
        "duplicate_snapshot",
        "snapshot_id",
        "evaluated_snapshots",
        "evaluated_items",
        "insufficient_data",
        "quality_label",
        "recommended_action",
        "warnings_count",
    ]:
        if key in summary:
            print(f"{key}={summary.get(key)}")
    if data.get("warnings"):
        print("warnings=" + ",".join(data.get("warnings") or []))
    if data.get("errors"):
        print("errors=" + ",".join(data.get("errors") or []))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Market data refresh and conservative overlay paper daily ops")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="Show market and paper tracking status")
    status_parser.add_argument("--stale-days", type=int, default=3)
    status_parser.add_argument("--json", action="store_true")

    refresh_parser = subparsers.add_parser("refresh", help="Refresh recent MOEX market data")
    refresh_parser.add_argument("--max-tickers", type=int, default=150)
    refresh_parser.add_argument("--days", type=int, default=120)
    refresh_parser.add_argument("--dry-run", action="store_true")
    refresh_parser.add_argument("--force", action="store_true")
    refresh_parser.add_argument("--json", action="store_true")

    run_parser = subparsers.add_parser("run", help="Run market daily ops workflow")
    run_parser.add_argument("--name", default="daily")
    run_parser.add_argument("--limit", type=int, default=100)
    run_parser.add_argument("--candles-limit", type=int, default=240)
    run_parser.add_argument("--horizon-days", type=int, default=20)
    run_parser.add_argument("--refresh-max-tickers", type=int, default=150)
    run_parser.add_argument("--refresh-days", type=int, default=120)
    run_parser.add_argument("--dry-run", action="store_true")
    run_parser.add_argument("--no-refresh", action="store_true")
    run_parser.add_argument("--force-refresh", action="store_true")
    run_parser.add_argument("--no-evaluate-ready", action="store_true")
    run_parser.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    db = SessionLocal()
    try:
        if args.command == "status":
            result = build_daily_ops_status(db, stale_days=args.stale_days)
            full_json = args.json
        elif args.command == "refresh":
            result = refresh_market_data_daily(
                db,
                max_tickers=args.max_tickers,
                days=args.days,
                dry_run=args.dry_run,
                force=args.force,
            )
            full_json = args.json
        elif args.command == "run":
            result = run_market_daily_ops(
                db,
                name=args.name,
                limit=args.limit,
                candles_limit=args.candles_limit,
                horizon_days=args.horizon_days,
                refresh_market_data=not args.no_refresh,
                refresh_max_tickers=args.refresh_max_tickers,
                refresh_days=args.refresh_days,
                evaluate_ready=not args.no_evaluate_ready,
                dry_run=args.dry_run,
                force_refresh=args.force_refresh,
            )
            full_json = args.json
        else:
            parser.error("unknown command")
            return 2
        _print_json(result) if full_json else _print_compact(result)
        return 0 if result.get("ok") else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
