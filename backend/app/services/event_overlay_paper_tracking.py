from __future__ import annotations

import json
import csv
import io
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import asc, desc, select
from sqlalchemy.orm import Session

from app.models import Candle, EventOverlayPaperSnapshot, EventOverlayPaperSnapshotItem
from app.services.consumer_signals import _round, _to_float, normalize_conservative_event_overlay_mode
from app.services.event_aware_risk_overlay import get_conservative_event_risk_overlay_config
from app.services.event_overlay_paper_snapshot import PAPER_TRADING_NOTE, build_event_overlay_paper_snapshot


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _json_load(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _ensure_tables(db: Session) -> None:
    bind = db.get_bind()
    EventOverlayPaperSnapshot.__table__.create(bind=bind, checkfirst=True)
    EventOverlayPaperSnapshotItem.__table__.create(bind=bind, checkfirst=True)


def _today_iso() -> str:
    return date.today().isoformat()


def _date_or_none(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _market_regime_label(value: Any) -> str | None:
    if isinstance(value, dict):
        return value.get("regime") or value.get("label") or value.get("risk_regime")
    if value is None:
        return None
    return str(value)


def calculate_position_pnl_pct(realized_return_pct: float | None, position_size_pct: float | None) -> float | None:
    if realized_return_pct is None or position_size_pct is None:
        return None
    return realized_return_pct * position_size_pct / 100.0


def calculate_overlay_delta_pnl_pct(
    baseline_realized_pnl_pct: float | None,
    overlay_realized_pnl_pct: float | None,
) -> float | None:
    if baseline_realized_pnl_pct is None or overlay_realized_pnl_pct is None:
        return None
    return overlay_realized_pnl_pct - baseline_realized_pnl_pct


def classify_realized_outcome(realized_return_pct: float | None) -> str:
    if realized_return_pct is None:
        return "insufficient_data"
    if realized_return_pct > 0:
        return "positive"
    if realized_return_pct < 0:
        return "negative"
    return "timeout"


def is_snapshot_ready_to_evaluate(snapshot: dict[str, Any], *, as_of_date: str | None = None) -> bool:
    status = str(snapshot.get("status") or "").lower()
    if status not in {"open", "partially_evaluated"}:
        return False
    snapshot_date = _date_or_none(snapshot.get("snapshot_date"))
    as_of = _date_or_none(as_of_date) or date.today()
    if snapshot_date is None:
        return False
    horizon_days = int(snapshot.get("horizon_days") or 0)
    return snapshot_date + timedelta(days=horizon_days) <= as_of


def recommend_lifecycle_action(
    *,
    total_snapshots: int,
    ready_count: int,
    days_since_last_snapshot: int | None,
) -> str:
    if total_snapshots <= 0:
        return "create_snapshot"
    if ready_count > 0:
        return "evaluate_ready"
    if days_since_last_snapshot is None or days_since_last_snapshot >= 7:
        return "create_snapshot"
    return "wait"


def _snapshot_to_dict(row: EventOverlayPaperSnapshot, *, include_items: bool = False, items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    result = {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "snapshot_date": row.snapshot_date,
        "name": row.name,
        "source": row.source,
        "config_id": row.config_id,
        "overlay_mode": row.overlay_mode,
        "limit": row.limit,
        "candles_limit": row.candles_limit,
        "horizon_days": row.horizon_days,
        "baseline_total_exposure": row.baseline_total_exposure,
        "overlay_total_exposure": row.overlay_total_exposure,
        "exposure_reduction_pct": row.exposure_reduction_pct,
        "avg_multiplier": row.avg_multiplier,
        "risk_level_counts": _json_load(row.risk_level_counts_json, {}),
        "summary": _json_load(row.summary_json, {}),
        "status": row.status,
        "evaluated_at": row.evaluated_at.isoformat() if row.evaluated_at else None,
        "notes": row.notes,
        "detail_url": f"/signals/event-aware/conservative-overlay-paper-snapshots/{row.id}",
    }
    if include_items:
        result["items"] = items or []
    return result


def _snapshot_summary_with_eval(row: EventOverlayPaperSnapshot) -> dict[str, Any]:
    data = _snapshot_to_dict(row)
    evaluation = (_json_load(row.summary_json, {}) or {}).get("evaluation") or {}
    data.update(
        {
            "items": evaluation.get("items"),
            "evaluated_items": evaluation.get("evaluated_items"),
            "baseline_realized_pnl_pct": evaluation.get("baseline_realized_pnl_pct"),
            "overlay_realized_pnl_pct": evaluation.get("overlay_realized_pnl_pct"),
            "overlay_delta_pnl_pct": evaluation.get("overlay_delta_pnl_pct"),
        }
    )
    return data


def _item_to_dict(row: EventOverlayPaperSnapshotItem) -> dict[str, Any]:
    return {
        "id": row.id,
        "snapshot_id": row.snapshot_id,
        "ticker": row.ticker,
        "action": row.action,
        "recommendation": row.recommendation,
        "entry_price": row.entry_price,
        "entry_date": row.entry_date,
        "base_position_size_pct": row.base_position_size_pct,
        "overlay_position_size_pct": row.overlay_position_size_pct,
        "event_risk_score": row.event_risk_score,
        "event_risk_level": row.event_risk_level,
        "event_risk_multiplier": row.event_risk_multiplier,
        "event_risk_reasons": _json_load(row.event_risk_reasons_json, []),
        "matched_rules": _json_load(row.matched_rules_json, []),
        "target_price": row.target_price,
        "stop_price": row.stop_price,
        "target_probability_pct": row.target_probability_pct,
        "risk_reward_ratio": row.risk_reward_ratio,
        "sector": row.sector,
        "market_regime": row.market_regime,
        "row": _json_load(row.row_json, {}),
        "realized_price": row.realized_price,
        "realized_date": row.realized_date,
        "realized_return_pct": row.realized_return_pct,
        "baseline_realized_pnl_pct": row.baseline_realized_pnl_pct,
        "overlay_realized_pnl_pct": row.overlay_realized_pnl_pct,
        "overlay_delta_pnl_pct": row.overlay_delta_pnl_pct,
        "realized_outcome": row.realized_outcome,
        "evaluated_at": row.evaluated_at.isoformat() if row.evaluated_at else None,
    }


def _find_duplicate_snapshot(
    db: Session,
    *,
    snapshot_date: str,
    config_id: str,
    limit: int,
    horizon_days: int,
    overlay_mode: str,
) -> EventOverlayPaperSnapshot | None:
    return db.scalars(
        select(EventOverlayPaperSnapshot)
        .where(EventOverlayPaperSnapshot.snapshot_date == snapshot_date)
        .where(EventOverlayPaperSnapshot.config_id == config_id)
        .where(EventOverlayPaperSnapshot.limit == limit)
        .where(EventOverlayPaperSnapshot.horizon_days == horizon_days)
        .where(EventOverlayPaperSnapshot.overlay_mode == overlay_mode)
        .order_by(desc(EventOverlayPaperSnapshot.created_at), desc(EventOverlayPaperSnapshot.id))
        .limit(1)
    ).first()


def create_conservative_overlay_paper_snapshot(
    db: Session,
    *,
    name: str | None = None,
    limit: int = 100,
    candles_limit: int = 240,
    horizon_days: int = 20,
    overlay_mode: str = "soft_adjust",
    dedupe_same_day: bool = True,
) -> dict[str, Any]:
    _ensure_tables(db)
    mode = normalize_conservative_event_overlay_mode(overlay_mode)
    config = get_conservative_event_risk_overlay_config()
    snapshot_date = _today_iso()

    if dedupe_same_day:
        duplicate = _find_duplicate_snapshot(
            db,
            snapshot_date=snapshot_date,
            config_id=str(config.get("config_id")),
            limit=limit,
            horizon_days=horizon_days,
            overlay_mode=mode,
        )
        if duplicate is not None:
            return {
                "ok": True,
                "mode": "create_conservative_overlay_paper_snapshot",
                "snapshot_id": duplicate.id,
                "created": False,
                "duplicate": True,
                "summary": _json_load(duplicate.summary_json, {}),
                "snapshot": _snapshot_to_dict(duplicate),
            }

    current = build_event_overlay_paper_snapshot(
        db=db,
        limit=limit,
        candles_limit=candles_limit,
        conservative_event_overlay_mode=mode,
    )
    summary = current.get("summary") or {}
    row = EventOverlayPaperSnapshot(
        snapshot_date=snapshot_date,
        name=name,
        source="conservative_event_overlay_paper_tracking",
        config_id=str(config.get("config_id")),
        overlay_mode=mode,
        limit=limit,
        candles_limit=candles_limit,
        horizon_days=horizon_days,
        baseline_total_exposure=_to_float(summary.get("baseline_total_exposure")),
        overlay_total_exposure=_to_float(summary.get("overlay_total_exposure")),
        exposure_reduction_pct=_to_float(summary.get("exposure_reduction_pct")),
        avg_multiplier=_to_float(summary.get("avg_multiplier")),
        risk_level_counts_json=_json_dump(summary.get("risk_level_counts") or {}),
        summary_json=_json_dump(summary),
        status="open",
        notes=PAPER_TRADING_NOTE,
    )
    db.add(row)
    db.flush()

    for source_row in current.get("rows") or []:
        db.add(
            EventOverlayPaperSnapshotItem(
                snapshot_id=row.id,
                ticker=str(source_row.get("ticker") or "").upper(),
                action=source_row.get("action"),
                recommendation=source_row.get("recommendation"),
                entry_price=_to_float(source_row.get("price")),
                entry_date=source_row.get("trade_date") or snapshot_date,
                base_position_size_pct=_to_float(source_row.get("base_position_size_pct")),
                overlay_position_size_pct=_to_float(source_row.get("event_adjusted_position_size_pct")),
                event_risk_score=_to_float(source_row.get("event_risk_score")),
                event_risk_level=source_row.get("event_risk_level"),
                event_risk_multiplier=_to_float(source_row.get("event_risk_multiplier")),
                event_risk_reasons_json=_json_dump(source_row.get("top_reasons") or []),
                matched_rules_json=_json_dump(source_row.get("matched_rule_ids") or []),
                target_price=_to_float(source_row.get("target_price")),
                stop_price=_to_float(source_row.get("stop_loss")),
                target_probability_pct=_to_float(source_row.get("target_probability_pct")),
                risk_reward_ratio=_to_float(source_row.get("risk_reward_ratio")),
                sector=source_row.get("sector"),
                market_regime=_market_regime_label(source_row.get("market_regime")),
                row_json=_json_dump(source_row),
                realized_outcome="pending",
            )
        )

    db.commit()
    db.refresh(row)
    return {
        "ok": True,
        "mode": "create_conservative_overlay_paper_snapshot",
        "snapshot_id": row.id,
        "created": True,
        "duplicate": False,
        "summary": summary,
        "snapshot": _snapshot_to_dict(row),
    }


def list_event_overlay_paper_snapshots(
    db: Session,
    *,
    limit: int = 50,
    status: str | None = None,
) -> dict[str, Any]:
    _ensure_tables(db)
    query = select(EventOverlayPaperSnapshot)
    if status:
        query = query.where(EventOverlayPaperSnapshot.status == status)
    rows = db.scalars(
        query.order_by(desc(EventOverlayPaperSnapshot.created_at), desc(EventOverlayPaperSnapshot.id)).limit(limit)
    ).all()
    return {
        "ok": True,
        "mode": "list_conservative_overlay_paper_snapshots",
        "total": len(rows),
        "rows": [_snapshot_to_dict(row) for row in rows],
    }


def get_event_overlay_paper_snapshot_detail(
    db: Session,
    *,
    snapshot_id: int,
) -> dict[str, Any]:
    _ensure_tables(db)
    row = db.get(EventOverlayPaperSnapshot, snapshot_id)
    if row is None:
        return {"ok": False, "error": "snapshot_not_found", "snapshot_id": snapshot_id}
    items = db.scalars(
        select(EventOverlayPaperSnapshotItem)
        .where(EventOverlayPaperSnapshotItem.snapshot_id == snapshot_id)
        .order_by(asc(EventOverlayPaperSnapshotItem.ticker), asc(EventOverlayPaperSnapshotItem.id))
    ).all()
    item_dicts = [_item_to_dict(item) for item in items]
    return {
        "ok": True,
        "mode": "conservative_overlay_paper_snapshot_detail",
        "snapshot": _snapshot_to_dict(row, include_items=True, items=item_dicts),
        "summary": _build_items_summary(item_dicts),
        "items": item_dicts,
    }


def delete_event_overlay_paper_snapshot(
    db: Session,
    *,
    snapshot_id: int,
) -> dict[str, Any]:
    _ensure_tables(db)
    row = db.get(EventOverlayPaperSnapshot, snapshot_id)
    if row is None:
        return {
            "ok": False,
            "deleted": False,
            "error": "snapshot_not_found",
            "snapshot_id": snapshot_id,
        }
    items = db.scalars(
        select(EventOverlayPaperSnapshotItem).where(EventOverlayPaperSnapshotItem.snapshot_id == snapshot_id)
    ).all()
    for item in items:
        db.delete(item)
    db.delete(row)
    db.commit()
    return {
        "ok": True,
        "deleted": True,
        "snapshot_id": snapshot_id,
        "deleted_items": len(items),
    }


def _future_candle(
    db: Session,
    *,
    ticker: str,
    target_date: date,
) -> Candle | None:
    return db.scalars(
        select(Candle)
        .where(Candle.ticker == ticker)
        .where(Candle.trade_date >= target_date)
        .order_by(asc(Candle.trade_date), asc(Candle.id))
        .limit(1)
    ).first()


def _build_items_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    evaluated = [item for item in items if item.get("realized_outcome") not in (None, "pending")]
    sufficient = [item for item in evaluated if item.get("realized_outcome") != "insufficient_data"]
    baseline_values = [_to_float(item.get("baseline_realized_pnl_pct")) for item in sufficient]
    overlay_values = [_to_float(item.get("overlay_realized_pnl_pct")) for item in sufficient]
    delta_values = [_to_float(item.get("overlay_delta_pnl_pct")) for item in sufficient]
    returns = [_to_float(item.get("realized_return_pct")) for item in sufficient]
    returns = [value for value in returns if value is not None]
    return {
        "items": len(items),
        "evaluated_items": len(sufficient),
        "insufficient_data": sum(1 for item in evaluated if item.get("realized_outcome") == "insufficient_data"),
        "baseline_realized_pnl_pct": _round(sum(v for v in baseline_values if v is not None), 4),
        "overlay_realized_pnl_pct": _round(sum(v for v in overlay_values if v is not None), 4),
        "overlay_delta_pnl_pct": _round(sum(v for v in delta_values if v is not None), 4),
        "baseline_avg_return_pct": _round(sum(v for v in returns if v is not None) / len(returns), 3) if returns else None,
        "overlay_weighted_avg_return_pct": _round(sum(v for v in overlay_values if v is not None) / len(overlay_values), 4) if overlay_values else None,
    }


def evaluate_event_overlay_paper_snapshot(
    db: Session,
    *,
    snapshot_id: int,
    evaluation_date: str | None = None,
    horizon_days: int | None = None,
) -> dict[str, Any]:
    _ensure_tables(db)
    snapshot = db.get(EventOverlayPaperSnapshot, snapshot_id)
    if snapshot is None:
        return {"ok": False, "error": "snapshot_not_found", "snapshot_id": snapshot_id}

    items = db.scalars(
        select(EventOverlayPaperSnapshotItem).where(EventOverlayPaperSnapshotItem.snapshot_id == snapshot_id)
    ).all()
    evaluated_at = datetime.utcnow()
    by_risk_level: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "items": 0,
            "evaluated_items": 0,
            "baseline_realized_pnl_pct": 0.0,
            "overlay_realized_pnl_pct": 0.0,
            "overlay_delta_pnl_pct": 0.0,
        }
    )

    for item in items:
        entry_date = _date_or_none(item.entry_date) or _date_or_none(snapshot.snapshot_date) or date.today()
        target_date = _date_or_none(evaluation_date)
        if target_date is None:
            target_date = entry_date + timedelta(days=int(horizon_days or snapshot.horizon_days or 20))
        candle = _future_candle(db, ticker=item.ticker, target_date=target_date)
        if candle is None or item.entry_price in (None, 0) or candle.close is None:
            item.realized_outcome = "insufficient_data"
            item.evaluated_at = evaluated_at
            continue

        realized_price = float(candle.close)
        realized_return_pct = (realized_price - float(item.entry_price)) / float(item.entry_price) * 100.0
        baseline_pnl = calculate_position_pnl_pct(realized_return_pct, item.base_position_size_pct)
        overlay_pnl = calculate_position_pnl_pct(realized_return_pct, item.overlay_position_size_pct)
        delta_pnl = calculate_overlay_delta_pnl_pct(baseline_pnl, overlay_pnl)

        item.realized_price = _round(realized_price, 4)
        item.realized_date = candle.trade_date.isoformat() if candle.trade_date else None
        item.realized_return_pct = _round(realized_return_pct, 4)
        item.baseline_realized_pnl_pct = _round(baseline_pnl, 6)
        item.overlay_realized_pnl_pct = _round(overlay_pnl, 6)
        item.overlay_delta_pnl_pct = _round(delta_pnl, 6)
        item.realized_outcome = classify_realized_outcome(realized_return_pct)
        item.evaluated_at = evaluated_at

        level = item.event_risk_level or "unknown"
        bucket = by_risk_level[level]
        bucket["items"] += 1
        bucket["evaluated_items"] += 1
        bucket["baseline_realized_pnl_pct"] += baseline_pnl or 0.0
        bucket["overlay_realized_pnl_pct"] += overlay_pnl or 0.0
        bucket["overlay_delta_pnl_pct"] += delta_pnl or 0.0

    item_dicts = [_item_to_dict(item) for item in items]
    summary = _build_items_summary(item_dicts)
    summary["by_risk_level"] = {
        level: {
            **values,
            "baseline_realized_pnl_pct": _round(values.get("baseline_realized_pnl_pct"), 4),
            "overlay_realized_pnl_pct": _round(values.get("overlay_realized_pnl_pct"), 4),
            "overlay_delta_pnl_pct": _round(values.get("overlay_delta_pnl_pct"), 4),
        }
        for level, values in by_risk_level.items()
    }
    summary["top_positive_delta"] = sorted(
        item_dicts,
        key=lambda item: _to_float(item.get("overlay_delta_pnl_pct")) or 0.0,
        reverse=True,
    )[:10]
    summary["top_negative_delta"] = sorted(
        item_dicts,
        key=lambda item: _to_float(item.get("overlay_delta_pnl_pct")) or 0.0,
    )[:10]

    insufficient = summary.get("insufficient_data") or 0
    evaluated_items = summary.get("evaluated_items") or 0
    if evaluated_items <= 0 and insufficient > 0:
        snapshot.status = "open"
    elif insufficient > 0:
        snapshot.status = "partially_evaluated"
    else:
        snapshot.status = "evaluated"
    snapshot.evaluated_at = evaluated_at
    current_summary = _json_load(snapshot.summary_json, {})
    current_summary["evaluation"] = {
        key: value
        for key, value in summary.items()
        if key not in {"top_positive_delta", "top_negative_delta"}
    }
    snapshot.summary_json = _json_dump(current_summary)
    db.commit()

    return {
        "ok": True,
        "mode": "evaluate_conservative_overlay_paper_snapshot",
        "snapshot_id": snapshot_id,
        "summary": summary,
        "items": item_dicts,
    }


def get_ready_to_evaluate_snapshots(
    db: Session,
    *,
    as_of_date: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    _ensure_tables(db)
    as_of = (_date_or_none(as_of_date) or date.today()).isoformat()
    rows = db.scalars(
        select(EventOverlayPaperSnapshot)
        .where(EventOverlayPaperSnapshot.status.in_(["open", "partially_evaluated"]))
        .order_by(asc(EventOverlayPaperSnapshot.snapshot_date), asc(EventOverlayPaperSnapshot.id))
        .limit(limit * 3)
    ).all()
    ready = [
        row
        for row in rows
        if is_snapshot_ready_to_evaluate(_snapshot_to_dict(row), as_of_date=as_of)
    ][:limit]
    return {
        "ok": True,
        "mode": "ready_to_evaluate_snapshots",
        "as_of_date": as_of,
        "ready_count": len(ready),
        "snapshots": [_snapshot_to_dict(row) for row in ready],
    }


def bulk_evaluate_ready_snapshots(
    db: Session,
    *,
    as_of_date: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    ready = get_ready_to_evaluate_snapshots(db, as_of_date=as_of_date, limit=limit)
    results: list[dict[str, Any]] = []
    total_items = 0
    total_evaluated = 0
    total_insufficient = 0
    for snapshot in ready.get("snapshots") or []:
        result = evaluate_event_overlay_paper_snapshot(
            db,
            snapshot_id=int(snapshot.get("id")),
            evaluation_date=ready.get("as_of_date"),
        )
        summary = result.get("summary") or {}
        total_items += int(summary.get("items") or 0)
        total_evaluated += int(summary.get("evaluated_items") or 0)
        total_insufficient += int(summary.get("insufficient_data") or 0)
        results.append(
            {
                "snapshot_id": snapshot.get("id"),
                "ok": result.get("ok"),
                "summary": summary,
            }
        )
    return {
        "ok": True,
        "mode": "bulk_evaluate_ready_snapshots",
        "as_of_date": ready.get("as_of_date"),
        "requested_limit": limit,
        "evaluated_snapshots": len(results),
        "skipped_snapshots": max(0, int(ready.get("ready_count") or 0) - len(results)),
        "total_items": total_items,
        "total_evaluated_items": total_evaluated,
        "total_insufficient_data": total_insufficient,
        "results": results,
    }


def build_event_overlay_paper_lifecycle_status(
    db: Session,
    *,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    _ensure_tables(db)
    as_of = _date_or_none(as_of_date) or date.today()
    rows = db.scalars(
        select(EventOverlayPaperSnapshot)
        .order_by(desc(EventOverlayPaperSnapshot.created_at), desc(EventOverlayPaperSnapshot.id))
    ).all()
    ready = [
        row
        for row in rows
        if is_snapshot_ready_to_evaluate(_snapshot_to_dict(row), as_of_date=as_of.isoformat())
    ]
    statuses = Counter(row.status for row in rows)
    latest_snapshot_date = max((_date_or_none(row.snapshot_date) for row in rows), default=None)
    days_since_last = (as_of - latest_snapshot_date).days if latest_snapshot_date else None
    recommended_action = recommend_lifecycle_action(
        total_snapshots=len(rows),
        ready_count=len(ready),
        days_since_last_snapshot=days_since_last,
    )
    recommendations = []
    if recommended_action == "create_snapshot":
        recommendations.append("Create a new conservative overlay paper snapshot.")
    elif recommended_action == "evaluate_ready":
        recommendations.append("Evaluate ready paper snapshots with the explicit POST bulk endpoint.")
    elif recommended_action == "wait":
        recommendations.append("Wait until snapshot horizon is reached or create the next scheduled snapshot.")
    else:
        recommendations.append("No lifecycle action available.")
    return {
        "ok": True,
        "mode": "event_overlay_paper_lifecycle_status",
        "summary": {
            "total_snapshots": len(rows),
            "open_snapshots": statuses.get("open", 0),
            "ready_to_evaluate_snapshots": len(ready),
            "partially_evaluated_snapshots": statuses.get("partially_evaluated", 0),
            "evaluated_snapshots": statuses.get("evaluated", 0),
            "last_snapshot_date": latest_snapshot_date.isoformat() if latest_snapshot_date else None,
            "days_since_last_snapshot": days_since_last,
            "recommended_action": recommended_action,
            "recommendations": recommendations,
        },
        "ready_snapshots": [_snapshot_to_dict(row) for row in ready[:25]],
        "latest_snapshots": [_snapshot_to_dict(row) for row in rows[:10]],
    }


def build_event_overlay_paper_dashboard(
    db: Session,
    *,
    limit: int = 20,
) -> dict[str, Any]:
    _ensure_tables(db)
    snapshots = db.scalars(
        select(EventOverlayPaperSnapshot)
        .order_by(desc(EventOverlayPaperSnapshot.created_at), desc(EventOverlayPaperSnapshot.id))
        .limit(limit)
    ).all()
    lifecycle = build_event_overlay_paper_lifecycle_status(db)
    if not snapshots:
        return {
            "ok": True,
            "mode": "conservative_overlay_paper_dashboard",
            "summary": {
                "snapshots": 0,
                "total_snapshots": 0,
                "open_snapshots": 0,
                "ready_to_evaluate_snapshots": 0,
                "evaluated_snapshots": 0,
                "total_items": 0,
                "evaluated_items": 0,
                "aggregate_baseline_pnl_pct": 0.0,
                "aggregate_overlay_pnl_pct": 0.0,
                "aggregate_overlay_delta_pnl_pct": 0.0,
                "baseline_total_pnl_pct": 0.0,
                "overlay_total_pnl_pct": 0.0,
                "overlay_delta_pnl_pct": 0.0,
                "recommendation": "create_snapshot",
            },
            "recent_snapshots": [],
            "by_risk_level": {},
            "by_snapshot": [],
            "cumulative_curve": [],
            "limitations": ["No paper snapshots stored yet."],
        }

    ids = [snapshot.id for snapshot in snapshots]
    items = db.scalars(
        select(EventOverlayPaperSnapshotItem).where(EventOverlayPaperSnapshotItem.snapshot_id.in_(ids))
    ).all()
    by_risk: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "items": 0,
            "evaluated_items": 0,
            "baseline_realized_pnl_pct": 0.0,
            "overlay_realized_pnl_pct": 0.0,
            "overlay_delta_pnl_pct": 0.0,
            "multiplier_sum": 0.0,
            "multiplier_count": 0,
        }
    )
    by_snapshot_acc: dict[int, dict[str, Any]] = {
        snapshot.id: {
            "snapshot_id": snapshot.id,
            "date": snapshot.snapshot_date,
            "status": snapshot.status,
            "baseline_pnl": 0.0,
            "overlay_pnl": 0.0,
            "delta": 0.0,
            "evaluated_items": 0,
        }
        for snapshot in snapshots
    }
    baseline_total = 0.0
    overlay_total = 0.0
    delta_total = 0.0
    total_items = len(items)
    evaluated_items = 0
    realized_returns: list[float] = []
    overlay_pnls: list[float] = []
    exposure_reductions = [_to_float(snapshot.exposure_reduction_pct) for snapshot in snapshots]
    exposure_reductions = [value for value in exposure_reductions if value is not None]
    multipliers = [_to_float(snapshot.avg_multiplier) for snapshot in snapshots]
    multipliers = [value for value in multipliers if value is not None]
    for item in items:
        baseline = _to_float(item.baseline_realized_pnl_pct)
        overlay = _to_float(item.overlay_realized_pnl_pct)
        delta = _to_float(item.overlay_delta_pnl_pct)
        multiplier = _to_float(item.event_risk_multiplier)
        risk_bucket = by_risk[item.event_risk_level or "unknown"]
        risk_bucket["items"] += 1
        if multiplier is not None:
            risk_bucket["multiplier_sum"] += multiplier
            risk_bucket["multiplier_count"] += 1
        if baseline is None or overlay is None or delta is None:
            continue
        evaluated_items += 1
        baseline_total += baseline
        overlay_total += overlay
        delta_total += delta
        realized_return = _to_float(item.realized_return_pct)
        if realized_return is not None:
            realized_returns.append(realized_return)
        overlay_pnls.append(overlay)
        risk_bucket["evaluated_items"] += 1
        risk_bucket["baseline_realized_pnl_pct"] += baseline
        risk_bucket["overlay_realized_pnl_pct"] += overlay
        risk_bucket["overlay_delta_pnl_pct"] += delta
        snapshot_bucket = by_snapshot_acc.get(item.snapshot_id)
        if snapshot_bucket is not None:
            snapshot_bucket["baseline_pnl"] += baseline
            snapshot_bucket["overlay_pnl"] += overlay
            snapshot_bucket["delta"] += delta
            snapshot_bucket["evaluated_items"] += 1

    statuses = Counter(snapshot.status for snapshot in snapshots)
    by_snapshot = [
        {
            **row,
            "baseline_pnl": _round(row.get("baseline_pnl"), 4),
            "overlay_pnl": _round(row.get("overlay_pnl"), 4),
            "delta": _round(row.get("delta"), 4),
        }
        for row in sorted(by_snapshot_acc.values(), key=lambda row: (str(row.get("date") or ""), int(row.get("snapshot_id") or 0)))
    ]
    cumulative_curve = []
    cumulative_baseline = 0.0
    cumulative_overlay = 0.0
    for row in by_snapshot:
        cumulative_baseline += _to_float(row.get("baseline_pnl")) or 0.0
        cumulative_overlay += _to_float(row.get("overlay_pnl")) or 0.0
        cumulative_curve.append(
            {
                "date": row.get("date"),
                "snapshot_id": row.get("snapshot_id"),
                "cumulative_baseline_pnl": _round(cumulative_baseline, 4),
                "cumulative_overlay_pnl": _round(cumulative_overlay, 4),
                "cumulative_delta": _round(cumulative_overlay - cumulative_baseline, 4),
            }
        )
    best_snapshot = max(by_snapshot, key=lambda row: _to_float(row.get("delta")) or 0.0) if by_snapshot else None
    worst_snapshot = min(by_snapshot, key=lambda row: _to_float(row.get("delta")) or 0.0) if by_snapshot else None
    recommendation = (lifecycle.get("summary") or {}).get("recommended_action") or "wait"
    return {
        "ok": True,
        "mode": "conservative_overlay_paper_dashboard",
        "summary": {
            "snapshots": len(snapshots),
            "total_snapshots": len(snapshots),
            "open_snapshots": statuses.get("open", 0),
            "ready_to_evaluate_snapshots": (lifecycle.get("summary") or {}).get("ready_to_evaluate_snapshots", 0),
            "partially_evaluated_snapshots": statuses.get("partially_evaluated", 0),
            "evaluated_snapshots": statuses.get("evaluated", 0),
            "total_items": total_items,
            "evaluated_items": evaluated_items,
            "latest_snapshot_id": snapshots[0].id if snapshots else None,
            "aggregate_baseline_pnl_pct": _round(baseline_total, 4),
            "aggregate_overlay_pnl_pct": _round(overlay_total, 4),
            "aggregate_overlay_delta_pnl_pct": _round(delta_total, 4),
            "baseline_total_pnl_pct": _round(baseline_total, 4),
            "overlay_total_pnl_pct": _round(overlay_total, 4),
            "overlay_delta_pnl_pct": _round(delta_total, 4),
            "baseline_avg_return_pct": _round(sum(realized_returns) / len(realized_returns), 4) if realized_returns else None,
            "overlay_avg_return_pct": _round(sum(overlay_pnls) / len(overlay_pnls), 4) if overlay_pnls else None,
            "baseline_win_rate_pct": _round(sum(1 for value in realized_returns if value > 0) / len(realized_returns) * 100, 2) if realized_returns else None,
            "overlay_win_rate_pct": _round(sum(1 for value in overlay_pnls if value > 0) / len(overlay_pnls) * 100, 2) if overlay_pnls else None,
            "avg_exposure_reduction_pct": _round(sum(exposure_reductions) / len(exposure_reductions), 3) if exposure_reductions else None,
            "avg_multiplier": _round(sum(multipliers) / len(multipliers), 3) if multipliers else None,
            "best_snapshot": best_snapshot,
            "worst_snapshot": worst_snapshot,
            "latest_snapshot": _snapshot_to_dict(snapshots[0]) if snapshots else None,
            "recommendation": recommendation,
            "paper_trading_note": PAPER_TRADING_NOTE,
        },
        "latest_snapshot": _snapshot_to_dict(snapshots[0]) if snapshots else None,
        "recent_snapshots": [_snapshot_to_dict(snapshot) for snapshot in snapshots],
        "by_risk_level": {
            level: {
                "items": values.get("items", 0),
                "evaluated_items": values.get("evaluated_items", 0),
                "baseline_realized_pnl_pct": _round(values.get("baseline_realized_pnl_pct"), 4),
                "overlay_realized_pnl_pct": _round(values.get("overlay_realized_pnl_pct"), 4),
                "overlay_delta_pnl_pct": _round(values.get("overlay_delta_pnl_pct"), 4),
                "avg_multiplier": _round(
                    values.get("multiplier_sum", 0.0) / values.get("multiplier_count", 1),
                    3,
                )
                if values.get("multiplier_count")
                else None,
            }
            for level, values in by_risk.items()
        },
        "by_snapshot": by_snapshot,
        "cumulative_curve": cumulative_curve,
        "limitations": [
            "Paper tracking uses saved snapshots and local candles only.",
            "No real orders are created.",
            "Evaluation is a close-to-close proxy and does not model execution quality.",
            "No investment advice.",
        ],
    }


def _csv_text(headers: list[str], rows: list[dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key) for key in headers})
    return output.getvalue()


def build_event_overlay_paper_snapshots_csv(
    db: Session,
    *,
    limit: int = 100,
    status: str | None = None,
) -> str:
    data = list_event_overlay_paper_snapshots(db, limit=limit, status=status)
    rows = []
    for row in data.get("rows") or []:
        summary = row.get("summary") or {}
        evaluation = summary.get("evaluation") or {}
        rows.append(
            {
                "snapshot_id": row.get("id"),
                "snapshot_date": row.get("snapshot_date"),
                "created_at": row.get("created_at"),
                "status": row.get("status"),
                "items": evaluation.get("items"),
                "baseline_total_exposure": row.get("baseline_total_exposure"),
                "overlay_total_exposure": row.get("overlay_total_exposure"),
                "exposure_reduction_pct": row.get("exposure_reduction_pct"),
                "avg_multiplier": row.get("avg_multiplier"),
                "baseline_realized_pnl_pct": evaluation.get("baseline_realized_pnl_pct"),
                "overlay_realized_pnl_pct": evaluation.get("overlay_realized_pnl_pct"),
                "overlay_delta_pnl_pct": evaluation.get("overlay_delta_pnl_pct"),
                "evaluated_at": row.get("evaluated_at"),
            }
        )
    return _csv_text(
        [
            "snapshot_id",
            "snapshot_date",
            "created_at",
            "status",
            "items",
            "baseline_total_exposure",
            "overlay_total_exposure",
            "exposure_reduction_pct",
            "avg_multiplier",
            "baseline_realized_pnl_pct",
            "overlay_realized_pnl_pct",
            "overlay_delta_pnl_pct",
            "evaluated_at",
        ],
        rows,
    )


def build_event_overlay_paper_snapshot_items_csv(
    db: Session,
    *,
    snapshot_id: int,
) -> str:
    data = get_event_overlay_paper_snapshot_detail(db, snapshot_id=snapshot_id)
    rows = [
        {
            "ticker": item.get("ticker"),
            "action": item.get("action"),
            "entry_date": item.get("entry_date"),
            "entry_price": item.get("entry_price"),
            "base_position_size_pct": item.get("base_position_size_pct"),
            "overlay_position_size_pct": item.get("overlay_position_size_pct"),
            "event_risk_score": item.get("event_risk_score"),
            "event_risk_level": item.get("event_risk_level"),
            "event_risk_multiplier": item.get("event_risk_multiplier"),
            "realized_date": item.get("realized_date"),
            "realized_price": item.get("realized_price"),
            "realized_return_pct": item.get("realized_return_pct"),
            "baseline_realized_pnl_pct": item.get("baseline_realized_pnl_pct"),
            "overlay_realized_pnl_pct": item.get("overlay_realized_pnl_pct"),
            "overlay_delta_pnl_pct": item.get("overlay_delta_pnl_pct"),
            "realized_outcome": item.get("realized_outcome"),
        }
        for item in data.get("items") or []
    ]
    return _csv_text(
        [
            "ticker",
            "action",
            "entry_date",
            "entry_price",
            "base_position_size_pct",
            "overlay_position_size_pct",
            "event_risk_score",
            "event_risk_level",
            "event_risk_multiplier",
            "realized_date",
            "realized_price",
            "realized_return_pct",
            "baseline_realized_pnl_pct",
            "overlay_realized_pnl_pct",
            "overlay_delta_pnl_pct",
            "realized_outcome",
        ],
        rows,
    )


def build_event_overlay_paper_dashboard_csv(db: Session) -> str:
    data = build_event_overlay_paper_dashboard(db, limit=100)
    summary = data.get("summary") or {}
    rows = [{"metric": key, "value": value} for key, value in summary.items() if not isinstance(value, (dict, list))]
    return _csv_text(["metric", "value"], rows)
