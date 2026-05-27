from __future__ import annotations

import argparse
import json
import sys

from app.db import SessionLocal
from app.services.historical_event_bootstrap import bootstrap_historical_events


def main() -> int:
    parser = argparse.ArgumentParser(description="Import curated historical market events into the local DB.")
    parser.add_argument("--seed-path", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace-existing-seed", action="store_true")
    parser.add_argument("--max-events", type=int, default=10000)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = bootstrap_historical_events(
            db,
            seed_path=args.seed_path,
            dry_run=args.dry_run,
            replace_existing_seed=args.replace_existing_seed,
            max_events=args.max_events,
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    finally:
        db.close()

    compact = {
        "ok": result.get("ok"),
        "mode": result.get("mode"),
        "dry_run": result.get("dry_run"),
        "seed_path": result.get("seed_path"),
        "total_loaded": result.get("total_loaded"),
        "valid_events": result.get("valid_events"),
        "inserted": result.get("inserted"),
        "updated": result.get("updated"),
        "skipped": result.get("skipped"),
        "date_range": result.get("date_range"),
        "by_event_family": result.get("by_event_family"),
        "warnings": result.get("warnings"),
        "errors": result.get("errors"),
    }
    print(json.dumps(compact, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
