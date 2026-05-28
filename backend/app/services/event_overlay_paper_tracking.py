from __future__ import annotations

import json
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
    if not snapshots:
        return {
            "ok": True,
            "mode": "conservative_overlay_paper_dashboard",
            "summary": {
                "snapshots": 0,
                "open_snapshots": 0,
                "evaluated_snapshots": 0,
                "aggregate_baseline_pnl_pct": 0.0,
                "aggregate_overlay_pnl_pct": 0.0,
                "aggregate_overlay_delta_pnl_pct": 0.0,
            },
            "recent_snapshots": [],
            "by_risk_level": {},
            "limitations": ["No paper snapshots stored yet."],
        }

    ids = [snapshot.id for snapshot in snapshots]
    items = db.scalars(
        select(EventOverlayPaperSnapshotItem).where(EventOverlayPaperSnapshotItem.snapshot_id.in_(ids))
    ).all()
    by_risk: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"items": 0, "baseline_realized_pnl_pct": 0.0, "overlay_realized_pnl_pct": 0.0, "overlay_delta_pnl_pct": 0.0}
    )
    baseline_total = 0.0
    overlay_total = 0.0
    delta_total = 0.0
    for item in items:
        baseline = _to_float(item.baseline_realized_pnl_pct)
        overlay = _to_float(item.overlay_realized_pnl_pct)
        delta = _to_float(item.overlay_delta_pnl_pct)
        if baseline is None or overlay is None or delta is None:
            continue
        baseline_total += baseline
        overlay_total += overlay
        delta_total += delta
        bucket = by_risk[item.event_risk_level or "unknown"]
        bucket["items"] += 1
        bucket["baseline_realized_pnl_pct"] += baseline
        bucket["overlay_realized_pnl_pct"] += overlay
        bucket["overlay_delta_pnl_pct"] += delta

    statuses = Counter(snapshot.status for snapshot in snapshots)
    return {
        "ok": True,
        "mode": "conservative_overlay_paper_dashboard",
        "summary": {
            "snapshots": len(snapshots),
            "open_snapshots": statuses.get("open", 0),
            "partially_evaluated_snapshots": statuses.get("partially_evaluated", 0),
            "evaluated_snapshots": statuses.get("evaluated", 0),
            "latest_snapshot_id": snapshots[0].id if snapshots else None,
            "aggregate_baseline_pnl_pct": _round(baseline_total, 4),
            "aggregate_overlay_pnl_pct": _round(overlay_total, 4),
            "aggregate_overlay_delta_pnl_pct": _round(delta_total, 4),
            "paper_trading_note": PAPER_TRADING_NOTE,
        },
        "latest_snapshot": _snapshot_to_dict(snapshots[0]) if snapshots else None,
        "recent_snapshots": [_snapshot_to_dict(snapshot) for snapshot in snapshots],
        "by_risk_level": {
            level: {
                **values,
                "baseline_realized_pnl_pct": _round(values.get("baseline_realized_pnl_pct"), 4),
                "overlay_realized_pnl_pct": _round(values.get("overlay_realized_pnl_pct"), 4),
                "overlay_delta_pnl_pct": _round(values.get("overlay_delta_pnl_pct"), 4),
            }
            for level, values in by_risk.items()
        },
        "limitations": [
            "Paper tracking uses saved snapshots and local candles only.",
            "No real orders are created.",
            "Evaluation is a close-to-close proxy and does not model execution quality.",
            "No investment advice.",
        ],
    }
