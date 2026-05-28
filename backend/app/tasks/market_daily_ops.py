from __future__ import annotations

import argparse
import json
import sys
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


def _build_progress_callback(enabled: bool):
    if not enabled:
        return None

    def _progress(event: dict[str, Any]) -> None:
        name = event.get("event")
        if name == "universe_start":
            print(
                f"[refresh] universe refresh start timeout={event.get('request_timeout')} retries={event.get('max_retries')}",
                file=sys.stderr,
                flush=True,
            )
        elif name == "universe_failed":
            print(f"[refresh] universe refresh failed: {event.get('errors')}", file=sys.stderr, flush=True)
        elif name == "universe_done":
            print(f"[refresh] universe refresh done unique={event.get('unique_tickers')}", file=sys.stderr, flush=True)
        elif name == "candles_start":
            print(
                f"[refresh] candles refresh start tickers={event.get('total')} days={event.get('days')}",
                file=sys.stderr,
                flush=True,
            )
        elif name == "ticker_start":
            print(f"[{event.get('index')}/{event.get('total')}] {event.get('ticker')} start", file=sys.stderr, flush=True)
        elif name == "ticker_done":
            print(
                f"[{event.get('index')}/{event.get('total')}] {event.get('ticker')} updated "
                f"inserted={event.get('inserted')} updated={event.get('updated')}",
                file=sys.stderr,
                flush=True,
            )
        elif name == "ticker_failed":
            print(
                f"[{event.get('index')}/{event.get('total')}] {event.get('ticker')} failed "
                f"{event.get('error_type')}: {event.get('error')}",
                file=sys.stderr,
                flush=True,
            )
        elif name == "max_runtime_exceeded":
            print(f"[refresh] max runtime exceeded seconds={event.get('max_runtime_seconds')}", file=sys.stderr, flush=True)
        elif name == "refresh_done":
            print(
                f"[refresh] completed loaded={event.get('loaded_tickers')} failed={event.get('failed_tickers')} "
                f"runtime={event.get('runtime_seconds')}s",
                file=sys.stderr,
                flush=True,
            )

    return _progress


def _add_refresh_hardening_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--request-timeout", type=float, default=10.0)
    parser.add_argument("--max-retries", type=int, default=1)
    parser.add_argument("--retry-backoff", type=float, default=0.5)
    parser.add_argument("--max-runtime-seconds", type=int, default=None)
    parser.add_argument("--skip-universe-refresh", action="store_true")
    parser.add_argument("--no-fallback-universe", action="store_true")
    parser.add_argument("--no-progress", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")


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
    _add_refresh_hardening_args(refresh_parser)

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
    _add_refresh_hardening_args(run_parser)

    args = parser.parse_args(argv)
    db = SessionLocal()
    try:
        if args.command == "status":
            result = build_daily_ops_status(db, stale_days=args.stale_days)
            full_json = args.json
        elif args.command == "refresh":
            progress_callback = _build_progress_callback(not args.no_progress)
            result = refresh_market_data_daily(
                db,
                max_tickers=args.max_tickers,
                days=args.days,
                dry_run=args.dry_run,
                force=args.force,
                request_timeout=args.request_timeout,
                max_retries=args.max_retries,
                retry_backoff=args.retry_backoff,
                refresh_universe=not args.skip_universe_refresh,
                fallback_to_existing_universe=not args.no_fallback_universe,
                continue_on_error=not args.fail_fast,
                max_runtime_seconds=args.max_runtime_seconds,
                progress_callback=progress_callback,
            )
            full_json = args.json
        elif args.command == "run":
            progress_callback = _build_progress_callback(not args.no_progress and not args.no_refresh)
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
                request_timeout=args.request_timeout,
                max_retries=args.max_retries,
                retry_backoff=args.retry_backoff,
                refresh_universe=not args.skip_universe_refresh,
                fallback_to_existing_universe=not args.no_fallback_universe,
                continue_on_error=not args.fail_fast,
                max_runtime_seconds=args.max_runtime_seconds,
                progress_callback=progress_callback,
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
