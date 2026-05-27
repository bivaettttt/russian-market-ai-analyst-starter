from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models import MarketEvent
from app.services.event_ticker_mapping import classify_event_family


DEFAULT_SEED_PATH = Path(__file__).resolve().parents[1] / "data" / "seed" / "historical_events_seed.json"


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except Exception:
            pass
        return [item.strip() for item in text.replace(";", ",").split(",") if item.strip()]
    return [str(value).strip()] if str(value).strip() else []


def _stable_event_id(event: dict[str, Any]) -> str:
    value = str(event.get("event_id") or "").strip()
    if value:
        return value
    basis = "|".join(
        [
            str(event.get("date") or event.get("published_at") or ""),
            str(event.get("title") or ""),
            str(event.get("source") or ""),
        ]
    )
    digest = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]
    return f"seed_{digest}"


def _parse_date(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d")
        except Exception:
            return None


def load_seed_events(seed_path: str | Path | None = None) -> list[dict[str, Any]]:
    path = Path(seed_path) if seed_path else DEFAULT_SEED_PATH
    if not path.exists():
        raise FileNotFoundError(f"Seed file not found: {path}")
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("events") or []
        if not isinstance(data, list):
            raise ValueError("JSON seed must be a list or an object with events list")
        return [dict(item) for item in data if isinstance(item, dict)]
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8", newline="") as fh:
            return [dict(row) for row in csv.DictReader(fh)]
    raise ValueError(f"Unsupported seed format: {path.suffix}")


def normalize_seed_event(event: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(event)
    event_date = _parse_date(normalized.get("date") or normalized.get("published_at") or normalized.get("created_at"))
    if event_date is None:
        raise ValueError("event date is required and must be YYYY-MM-DD compatible")
    title = str(normalized.get("title") or "").strip()
    if not title:
        raise ValueError("event title is required")

    normalized["event_id"] = _stable_event_id(normalized)
    normalized["date"] = event_date.date().isoformat()
    normalized["created_at"] = event_date
    normalized["title"] = title
    normalized["summary"] = str(normalized.get("summary") or normalized.get("text") or title).strip()
    normalized["source"] = str(normalized.get("source") or "curated_seed").strip()
    normalized["url"] = str(normalized.get("url") or "").strip()
    normalized["tags"] = _as_list(normalized.get("tags"))
    normalized["affected_sectors"] = _as_list(normalized.get("affected_sectors"))
    normalized["affected_asset_types"] = _as_list(normalized.get("affected_asset_types"))
    normalized["affected_tickers"] = [item.upper() for item in _as_list(normalized.get("affected_tickers"))]

    mapped = classify_event_family(normalized)
    normalized["event_family"] = str(normalized.get("event_family") or mapped.get("event_family") or "unknown")
    normalized["direction"] = str(normalized.get("direction") or mapped.get("direction") or "unknown")
    normalized["impact_scope"] = str(normalized.get("impact_scope") or mapped.get("impact_scope") or "unknown")
    normalized["score"] = int(float(normalized.get("score") if normalized.get("score") is not None else mapped.get("score") or 0))
    normalized["confidence"] = str(normalized.get("confidence") or mapped.get("confidence") or "low")
    if normalized["event_family"] == "unknown" and not normalized["tags"]:
        raise ValueError("event_family or tags are required")
    return normalized


def _raw_analysis(event: dict[str, Any]) -> str:
    raw = {
        "event_id": event["event_id"],
        "date": event["date"],
        "event_family": event["event_family"],
        "event_type": event["event_family"],
        "direction": event["direction"],
        "impact_scope": event["impact_scope"],
        "affected_sectors": event["affected_sectors"],
        "affected_asset_types": event["affected_asset_types"],
        "affected_tickers": event["affected_tickers"],
        "affected_assets": event["affected_tickers"],
        "tags": event["tags"],
        "score": event["score"],
        "confidence": event["confidence"],
        "importance": max(1, min(10, int(abs(event["score"]) / 10) or 3)),
        "impact": event["direction"],
        "time_horizon": "1-4w",
        "reasoning": event.get("summary") or event["title"],
        "curated_seed": True,
    }
    return json.dumps(raw, ensure_ascii=False, sort_keys=True)


def _index_existing_seed_events(db: Session, *, source: str) -> dict[str, MarketEvent]:
    existing: dict[str, MarketEvent] = {}
    rows = db.query(MarketEvent).filter(MarketEvent.source == source).all()
    for row in rows:
        raw = getattr(row, "raw_analysis", None)
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except Exception:
            continue
        event_id = str(parsed.get("event_id") or "").strip()
        if event_id:
            existing[event_id] = row
    return existing


def _apply_events(
    db: Session,
    events: list[dict[str, Any]],
    *,
    dry_run: bool,
    replace_existing_seed: bool,
) -> tuple[int, int, int]:
    inserted = 0
    updated = 0
    skipped = 0
    source = "curated_seed"
    existing = _index_existing_seed_events(db, source=source)
    if replace_existing_seed and not dry_run:
        for row in existing.values():
            db.delete(row)
        db.flush()
        existing = {}

    for event in events:
        raw_analysis = _raw_analysis(event)
        affected_assets = json.dumps(event["affected_tickers"], ensure_ascii=False)
        row = existing.get(event["event_id"])
        if row is None:
            inserted += 1
            if not dry_run:
                db.add(
                    MarketEvent(
                        title=event["title"],
                        text=event["summary"],
                        source=event["source"],
                        url=event["url"] or None,
                        importance=max(1, min(10, int(abs(event["score"]) / 10) or 3)),
                        impact=event["direction"],
                        affected_assets=affected_assets,
                        reasoning=event["summary"],
                        raw_analysis=raw_analysis,
                        created_at=event["created_at"],
                    )
                )
        else:
            updated += 1
            if not dry_run:
                row.title = event["title"]
                row.text = event["summary"]
                row.source = event["source"]
                row.url = event["url"] or None
                row.importance = max(1, min(10, int(abs(event["score"]) / 10) or 3))
                row.impact = event["direction"]
                row.affected_assets = affected_assets
                row.reasoning = event["summary"]
                row.raw_analysis = raw_analysis
                row.created_at = event["created_at"]
    return inserted, updated, skipped


def _summary(
    *,
    seed_path: str,
    dry_run: bool,
    loaded: int,
    valid_events: list[dict[str, Any]],
    inserted: int,
    updated: int,
    skipped: int,
    errors: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    dates = [event["date"] for event in valid_events]
    return {
        "ok": not errors or bool(valid_events),
        "mode": "historical_event_bootstrap",
        "seed_path": seed_path,
        "dry_run": dry_run,
        "total_loaded": loaded,
        "valid_events": len(valid_events),
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "warnings": warnings,
        "by_event_family": dict(Counter(event["event_family"] for event in valid_events)),
        "by_direction": dict(Counter(event["direction"] for event in valid_events)),
        "date_range": {"first_date": min(dates), "last_date": max(dates)} if dates else {},
    }


def import_historical_events_from_file(
    db: Session,
    *,
    path: str,
    dry_run: bool = False,
    replace_existing_seed: bool = False,
    max_events: int = 10000,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    loaded_rows = load_seed_events(path)[:max_events]
    valid: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(loaded_rows, start=1):
        try:
            event = normalize_seed_event(row)
            if event["event_id"] in seen_ids:
                warnings.append(f"duplicate seed event_id skipped at row {index}: {event['event_id']}")
                continue
            seen_ids.add(event["event_id"])
            valid.append(event)
        except Exception as exc:
            errors.append(f"row {index}: {exc}")
    inserted, updated, skipped = _apply_events(db, valid, dry_run=dry_run, replace_existing_seed=replace_existing_seed)
    if not dry_run:
        db.commit()
    return _summary(
        seed_path=str(path),
        dry_run=dry_run,
        loaded=len(loaded_rows),
        valid_events=valid,
        inserted=inserted,
        updated=updated,
        skipped=skipped,
        errors=errors,
        warnings=warnings,
    )


def bootstrap_historical_events(
    db: Session,
    *,
    seed_path: str | None = None,
    dry_run: bool = False,
    replace_existing_seed: bool = False,
    max_events: int = 10000,
) -> dict[str, Any]:
    path = str(Path(seed_path) if seed_path else DEFAULT_SEED_PATH)
    return import_historical_events_from_file(
        db,
        path=path,
        dry_run=dry_run,
        replace_existing_seed=replace_existing_seed,
        max_events=max_events,
    )
