from __future__ import annotations

import argparse
import json
import sys

from app.db import Base, SessionLocal, engine
from app.services.market_universe import ensure_instrument_classification_schema
from app.services.moex_data_bootstrap import (
    bootstrap_market_data,
    bootstrap_moex_candles,
    bootstrap_moex_universe,
    normalize_tickers,
)


def _print_summary(result: dict) -> None:
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if result.get("mode") == "bootstrap_market_data":
        universe = result.get("universe") or {}
        candles = result.get("candles") or {}
        print(
            "\nSUMMARY "
            f"universe_unique={universe.get('unique_tickers')} "
            f"universe_inserted={universe.get('inserted')} "
            f"candles_loaded_tickers={candles.get('loaded_tickers')} "
            f"inserted_candles={candles.get('inserted_candles')} "
            f"updated_candles={candles.get('updated_candles')} "
            f"dry_run={result.get('dry_run')}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap local MOEX universe and daily candles.")
    parser.add_argument("--max-instruments", type=int, default=500)
    parser.add_argument("--max-tickers", type=int, default=150)
    parser.add_argument("--days", type=int, default=900)
    parser.add_argument("--from-date", default=None)
    parser.add_argument("--till-date", default=None)
    parser.add_argument("--include-etf", dest="include_etf", action="store_true", default=True)
    parser.add_argument("--no-include-etf", dest="include_etf", action="store_false")
    parser.add_argument("--include-bonds", action="store_true")
    parser.add_argument("--timeout-sec", type=float, default=20.0)
    parser.add_argument("--sleep-sec", type=float, default=0.15)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--tickers", default=None, help="Comma-separated tickers, for example SBER,GAZP,LKOH.")
    parser.add_argument("--skip-universe", action="store_true")
    parser.add_argument("--skip-candles", action="store_true")
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    ensure_instrument_classification_schema(engine)
    db = SessionLocal()
    try:
        tickers = normalize_tickers(args.tickers)
        if args.skip_universe and args.skip_candles:
            result = {"ok": False, "mode": "bootstrap_market_data", "errors": ["Both --skip-universe and --skip-candles were set."]}
        elif args.skip_universe:
            result = bootstrap_moex_candles(
                db,
                tickers=tickers,
                max_tickers=args.max_tickers,
                days=args.days,
                from_date=args.from_date,
                till_date=args.till_date,
                timeout_sec=args.timeout_sec,
                sleep_sec=args.sleep_sec,
                dry_run=args.dry_run,
            )
        elif args.skip_candles:
            result = bootstrap_moex_universe(
                db,
                max_instruments=args.max_instruments,
                include_etf=args.include_etf,
                include_bonds=args.include_bonds,
                timeout_sec=args.timeout_sec,
                dry_run=args.dry_run,
            )
        elif tickers or args.from_date or args.till_date:
            universe = bootstrap_moex_universe(
                db,
                max_instruments=args.max_instruments,
                include_etf=args.include_etf,
                include_bonds=args.include_bonds,
                timeout_sec=args.timeout_sec,
                dry_run=args.dry_run,
            )
            candles = bootstrap_moex_candles(
                db,
                tickers=tickers,
                max_tickers=args.max_tickers,
                days=args.days,
                from_date=args.from_date,
                till_date=args.till_date,
                timeout_sec=args.timeout_sec,
                sleep_sec=args.sleep_sec,
                dry_run=args.dry_run,
            )
            result = {
                "ok": bool(universe.get("ok")) and bool(candles.get("ok")),
                "mode": "bootstrap_market_data",
                "dry_run": args.dry_run,
                "universe": universe,
                "candles": candles,
                "errors": [*universe.get("errors", []), *[item.get("error") for item in candles.get("failed", []) if item.get("error")]],
                "warnings": [*universe.get("warnings", []), *candles.get("warnings", [])],
            }
        else:
            result = bootstrap_market_data(
                db,
                max_instruments=args.max_instruments,
                max_tickers=args.max_tickers,
                days=args.days,
                include_etf=args.include_etf,
                include_bonds=args.include_bonds,
                timeout_sec=args.timeout_sec,
                sleep_sec=args.sleep_sec,
                dry_run=args.dry_run,
            )
        _print_summary(result)
        sys.exit(0 if result.get("ok") else 1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
