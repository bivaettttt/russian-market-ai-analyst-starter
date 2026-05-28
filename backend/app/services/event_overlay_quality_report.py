from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models import Candle, EventOverlayPaperSnapshot, EventOverlayPaperSnapshotItem, MarketEvent
from app.services.consumer_signals import _round, _to_float
from app.services.event_overlay_paper_tracking import (
    _csv_text,
    _date_or_none,
    _ensure_tables,
    _item_to_dict,
    _snapshot_to_dict,
    build_event_overlay_paper_lifecycle_status,
    bulk_evaluate_ready_snapshots,
    create_conservative_overlay_paper_snapshot,
    get_ready_to_evaluate_snapshots,
)


LIMITATIONS = [
    "Paper tracking only; no real orders are created.",
    "Realized outcomes depend on locally available future candles.",
    "Close-to-close evaluation is a validation proxy, not execution-grade accounting.",
    "No investment advice.",
]


def classify_overlay_quality(*, evaluated_items: int, overlay_delta_pnl_pct: float | None) -> str:
    if evaluated_items < 10 or overlay_delta_pnl_pct is None:
        return "insufficient_data"
    if overlay_delta_pnl_pct > 0.05:
        return "improving"
    if overlay_delta_pnl_pct < -0.05:
        return "underperforming"
    return "mixed"


def recommend_quality_action(
    *,
    snapshots_total: int,
    ready_to_evaluate: int,
    quality_label: str,
) -> str:
    if snapshots_total <= 0:
        return "create_snapshot"
    if ready_to_evaluate > 0:
        return "evaluate_ready"
    if quality_label == "underperforming":
        return "review_underperformance"
    if quality_label == "insufficient_data":
        return "continue_tracking"
    return "continue_tracking"


def aggregate_quality_cumulative_curve(snapshot_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cumulative_baseline = 0.0
    cumulative_overlay = 0.0
    curve: list[dict[str, Any]] = []
    for row in sorted(snapshot_rows, key=lambda item: (str(item.get("snapshot_date") or ""), int(item.get("snapshot_id") or 0))):
        baseline = _to_float(row.get("baseline_pnl_pct")) or 0.0
        overlay = _to_float(row.get("overlay_pnl_pct")) or 0.0
        cumulative_baseline += baseline
        cumulative_overlay += overlay
        curve.append(
            {
                "snapshot_date": row.get("snapshot_date"),
                "snapshot_id": row.get("snapshot_id"),
                "baseline_cumulative_pnl_pct": _round(cumulative_baseline, 4),
                "overlay_cumulative_pnl_pct": _round(cumulative_overlay, 4),
                "delta_cumulative_pnl_pct": _round(cumulative_overlay - cumulative_baseline, 4),
            }
        )
    return curve


def aggregate_quality_by_risk_level(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "risk_level": "unknown",
            "items": 0,
            "evaluated_items": 0,
            "baseline_pnl_pct": 0.0,
            "overlay_pnl_pct": 0.0,
            "delta_pnl_pct": 0.0,
            "multiplier_sum": 0.0,
            "multiplier_count": 0,
            "wins": 0,
        }
    )
    for item in items:
        level = str(item.get("event_risk_level") or "unknown")
        bucket = buckets[level]
        bucket["risk_level"] = level
        bucket["items"] += 1
        multiplier = _to_float(item.get("event_risk_multiplier"))
        if multiplier is not None:
            bucket["multiplier_sum"] += multiplier
            bucket["multiplier_count"] += 1
        baseline = _to_float(item.get("baseline_realized_pnl_pct"))
        overlay = _to_float(item.get("overlay_realized_pnl_pct"))
        delta = _to_float(item.get("overlay_delta_pnl_pct"))
        realized_return = _to_float(item.get("realized_return_pct"))
        if baseline is None or overlay is None or delta is None:
            continue
        bucket["evaluated_items"] += 1
        bucket["baseline_pnl_pct"] += baseline
        bucket["overlay_pnl_pct"] += overlay
        bucket["delta_pnl_pct"] += delta
        if realized_return is not None and realized_return > 0:
            bucket["wins"] += 1
    rows = []
    order = {"low": 0, "moderate": 1, "elevated": 2, "high": 3, "extreme": 4, "unknown": 5}
    for level, values in buckets.items():
        evaluated = int(values.get("evaluated_items") or 0)
        multiplier_count = int(values.get("multiplier_count") or 0)
        rows.append(
            {
                "risk_level": level,
                "items": int(values.get("items") or 0),
                "evaluated_items": evaluated,
                "baseline_pnl_pct": _round(values.get("baseline_pnl_pct"), 4),
                "overlay_pnl_pct": _round(values.get("overlay_pnl_pct"), 4),
                "delta_pnl_pct": _round(values.get("delta_pnl_pct"), 4),
                "avg_multiplier": _round(values.get("multiplier_sum", 0.0) / multiplier_count, 3) if multiplier_count else None,
                "win_rate_pct": _round(values.get("wins", 0) / evaluated * 100, 2) if evaluated else None,
            }
        )
    return sorted(rows, key=lambda row: order.get(str(row.get("risk_level")), 99))


def _safe_snapshot_summary(snapshot: EventOverlayPaperSnapshot) -> dict[str, Any]:
    return _snapshot_to_dict(snapshot).get("summary") or {}


def _load_quality_data(db: Session, *, limit: int, include_open_snapshots: bool) -> tuple[list[EventOverlayPaperSnapshot], list[EventOverlayPaperSnapshotItem]]:
    _ensure_tables(db)
    query = select(EventOverlayPaperSnapshot).order_by(desc(EventOverlayPaperSnapshot.created_at), desc(EventOverlayPaperSnapshot.id)).limit(limit)
    snapshots = list(db.scalars(query).all())
    if not include_open_snapshots:
        snapshots = [snapshot for snapshot in snapshots if snapshot.status in {"evaluated", "partially_evaluated"}]
    ids = [snapshot.id for snapshot in snapshots]
    if not ids:
        return snapshots, []
    items = list(db.scalars(select(EventOverlayPaperSnapshotItem).where(EventOverlayPaperSnapshotItem.snapshot_id.in_(ids))).all())
    return snapshots, items


def _snapshot_rows(snapshots: list[EventOverlayPaperSnapshot], items: list[EventOverlayPaperSnapshotItem]) -> list[dict[str, Any]]:
    by_snapshot: dict[int, dict[str, Any]] = {
        snapshot.id: {
            "snapshot_id": snapshot.id,
            "snapshot_date": snapshot.snapshot_date,
            "status": snapshot.status,
            "baseline_pnl_pct": 0.0,
            "overlay_pnl_pct": 0.0,
            "delta_pnl_pct": 0.0,
            "evaluated_items": 0,
            "items": 0,
            "avg_multiplier": snapshot.avg_multiplier,
            "exposure_reduction_pct": snapshot.exposure_reduction_pct,
        }
        for snapshot in snapshots
    }
    for item in items:
        row = by_snapshot.get(item.snapshot_id)
        if row is None:
            continue
        row["items"] += 1
        baseline = _to_float(item.baseline_realized_pnl_pct)
        overlay = _to_float(item.overlay_realized_pnl_pct)
        delta = _to_float(item.overlay_delta_pnl_pct)
        if baseline is None or overlay is None or delta is None:
            continue
        row["evaluated_items"] += 1
        row["baseline_pnl_pct"] += baseline
        row["overlay_pnl_pct"] += overlay
        row["delta_pnl_pct"] += delta
    return [
        {
            **row,
            "baseline_pnl_pct": _round(row.get("baseline_pnl_pct"), 4),
            "overlay_pnl_pct": _round(row.get("overlay_pnl_pct"), 4),
            "delta_pnl_pct": _round(row.get("delta_pnl_pct"), 4),
        }
        for row in by_snapshot.values()
    ]


def _problem_tickers(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "ticker": "",
            "items": 0,
            "negative_delta_count": 0,
            "delta_pnl_pct": 0.0,
            "missed_upside_count": 0,
            "avg_multiplier_sum": 0.0,
            "avg_multiplier_count": 0,
        }
    )
    for item in items:
        ticker = str(item.get("ticker") or "").upper()
        if not ticker:
            continue
        delta = _to_float(item.get("overlay_delta_pnl_pct"))
        realized_return = _to_float(item.get("realized_return_pct"))
        multiplier = _to_float(item.get("event_risk_multiplier"))
        bucket = buckets[ticker]
        bucket["ticker"] = ticker
        bucket["items"] += 1
        if multiplier is not None:
            bucket["avg_multiplier_sum"] += multiplier
            bucket["avg_multiplier_count"] += 1
        if delta is not None:
            bucket["delta_pnl_pct"] += delta
            if delta < 0:
                bucket["negative_delta_count"] += 1
        if realized_return is not None and realized_return > 0 and multiplier is not None and multiplier < 1:
            bucket["missed_upside_count"] += 1
    rows = []
    for bucket in buckets.values():
        if bucket["negative_delta_count"] <= 0 and bucket["missed_upside_count"] <= 0:
            continue
        count = bucket["avg_multiplier_count"]
        rows.append(
            {
                "ticker": bucket["ticker"],
                "items": bucket["items"],
                "negative_delta_count": bucket["negative_delta_count"],
                "missed_upside_count": bucket["missed_upside_count"],
                "delta_pnl_pct": _round(bucket["delta_pnl_pct"], 4),
                "avg_multiplier": _round(bucket["avg_multiplier_sum"] / count, 3) if count else None,
            }
        )
    return sorted(rows, key=lambda row: (_to_float(row.get("delta_pnl_pct")) or 0.0, -int(row.get("missed_upside_count") or 0)))[:20]


def build_conservative_overlay_quality_report(
    db: Session,
    *,
    limit: int = 30,
    include_open_snapshots: bool = True,
) -> dict[str, Any]:
    snapshots, item_rows = _load_quality_data(db, limit=limit, include_open_snapshots=include_open_snapshots)
    lifecycle = build_event_overlay_paper_lifecycle_status(db)
    lifecycle_summary = lifecycle.get("summary") or {}
    items = [_item_to_dict(item) for item in item_rows]
    snapshot_rows = _snapshot_rows(snapshots, item_rows)
    evaluated_items = [item for item in items if _to_float(item.get("overlay_delta_pnl_pct")) is not None]

    baseline_total = sum((_to_float(item.get("baseline_realized_pnl_pct")) or 0.0) for item in evaluated_items)
    overlay_total = sum((_to_float(item.get("overlay_realized_pnl_pct")) or 0.0) for item in evaluated_items)
    delta_total = sum((_to_float(item.get("overlay_delta_pnl_pct")) or 0.0) for item in evaluated_items)
    realized_returns = [_to_float(item.get("realized_return_pct")) for item in evaluated_items]
    realized_returns = [value for value in realized_returns if value is not None]
    overlay_pnls = [_to_float(item.get("overlay_realized_pnl_pct")) for item in evaluated_items]
    overlay_pnls = [value for value in overlay_pnls if value is not None]
    exposure_reductions = [_to_float(snapshot.exposure_reduction_pct) for snapshot in snapshots]
    exposure_reductions = [value for value in exposure_reductions if value is not None]
    multipliers = [_to_float(snapshot.avg_multiplier) for snapshot in snapshots]
    multipliers = [value for value in multipliers if value is not None]
    statuses = Counter(snapshot.status for snapshot in snapshots)
    quality_label = classify_overlay_quality(
        evaluated_items=len(evaluated_items),
        overlay_delta_pnl_pct=delta_total if evaluated_items else None,
    )
    ready = int(lifecycle_summary.get("ready_to_evaluate_snapshots") or 0)
    recommended_action = recommend_quality_action(
        snapshots_total=int(lifecycle_summary.get("total_snapshots") or len(snapshots)),
        ready_to_evaluate=ready,
        quality_label=quality_label,
    )
    best_snapshot = max(snapshot_rows, key=lambda row: _to_float(row.get("delta_pnl_pct")) or 0.0) if snapshot_rows else None
    worst_snapshot = min(snapshot_rows, key=lambda row: _to_float(row.get("delta_pnl_pct")) or 0.0) if snapshot_rows else None

    sorted_items_positive = sorted(evaluated_items, key=lambda item: _to_float(item.get("overlay_delta_pnl_pct")) or 0.0, reverse=True)
    sorted_items_negative = sorted(evaluated_items, key=lambda item: _to_float(item.get("overlay_delta_pnl_pct")) or 0.0)
    warnings = []
    if not snapshots:
        warnings.append("no_snapshots")
    if ready > 0:
        warnings.append("snapshots_ready_to_evaluate")
    if not evaluated_items:
        warnings.append("no_evaluated_items")
    if quality_label == "underperforming":
        warnings.append("overlay_underperforming")
    if any((_to_float(snapshot.baseline_total_exposure) or 0.0) <= 0 and int(((_safe_snapshot_summary(snapshot) or {}).get("rows") or 0)) > 0 for snapshot in snapshots):
        warnings.append("zero_exposure_snapshots_detected")

    return {
        "ok": True,
        "mode": "conservative_overlay_quality_report",
        "summary": {
            "snapshots_total": int(lifecycle_summary.get("total_snapshots") or len(snapshots)),
            "snapshots_evaluated": statuses.get("evaluated", 0),
            "snapshots_open": statuses.get("open", 0),
            "snapshots_ready": ready,
            "items_total": len(items),
            "items_evaluated": len(evaluated_items),
            "baseline_total_pnl_pct": _round(baseline_total, 4),
            "overlay_total_pnl_pct": _round(overlay_total, 4),
            "overlay_delta_pnl_pct": _round(delta_total, 4),
            "overlay_delta_positive": delta_total > 0,
            "avg_exposure_reduction_pct": _round(sum(exposure_reductions) / len(exposure_reductions), 3) if exposure_reductions else None,
            "avg_multiplier": _round(sum(multipliers) / len(multipliers), 3) if multipliers else None,
            "baseline_win_rate_pct": _round(sum(1 for value in realized_returns if value > 0) / len(realized_returns) * 100, 2) if realized_returns else None,
            "overlay_win_rate_pct": _round(sum(1 for value in overlay_pnls if value > 0) / len(overlay_pnls) * 100, 2) if overlay_pnls else None,
            "best_snapshot_id": best_snapshot.get("snapshot_id") if best_snapshot else None,
            "worst_snapshot_id": worst_snapshot.get("snapshot_id") if worst_snapshot else None,
            "last_snapshot_date": lifecycle_summary.get("last_snapshot_date"),
            "quality_label": quality_label,
            "recommended_action": recommended_action,
        },
        "cumulative_curve": aggregate_quality_cumulative_curve(snapshot_rows),
        "by_risk_level": aggregate_quality_by_risk_level(items),
        "top_positive_contributors": sorted_items_positive[:15],
        "top_negative_contributors": sorted_items_negative[:15],
        "problem_tickers": _problem_tickers(evaluated_items),
        "recent_snapshots": [_snapshot_to_dict(snapshot) for snapshot in snapshots],
        "warnings": warnings,
        "limitations": LIMITATIONS,
    }


def build_conservative_overlay_notification_summary(
    db: Session,
    *,
    limit: int = 30,
) -> dict[str, Any]:
    report = build_conservative_overlay_quality_report(db, limit=limit, include_open_snapshots=True)
    health = build_conservative_overlay_data_health(db)
    summary = report.get("summary") or {}
    health_summary = health.get("summary") or {}
    snapshots_total = int(summary.get("snapshots_total") or 0)
    ready = int(summary.get("snapshots_ready") or 0)
    quality_label = summary.get("quality_label") or "insufficient_data"
    delta = _to_float(summary.get("overlay_delta_pnl_pct"))
    if health_summary.get("market_data_stale"):
        status = "warning"
        days = health_summary.get("days_since_last_market_candle")
        message = f"Market data is stale by {days} days. Refresh market data before relying on paper results."
    elif snapshots_total <= 0:
        status = "needs_action"
        message = "No snapshots yet. Create the first paper snapshot."
    elif ready > 0:
        status = "needs_action"
        message = f"{ready} snapshots are ready to evaluate."
    elif quality_label == "improving":
        status = "ok"
        message = f"Overlay is ahead by {_round(delta, 4)} p.p. across {summary.get('snapshots_evaluated') or 0} evaluated snapshots."
    elif quality_label == "underperforming":
        status = "warning"
        message = "Overlay is underperforming; review problem tickers."
    else:
        status = "insufficient_data"
        message = "Paper tracking is active, but evaluated data is still insufficient."
    return {
        "ok": True,
        "mode": "conservative_overlay_notification_summary",
        "title": "Conservative Overlay Paper Tracking",
        "status": status,
        "message": message,
        "metrics": {
            "snapshots_total": snapshots_total,
            "ready_to_evaluate": ready,
            "baseline_pnl": summary.get("baseline_total_pnl_pct"),
            "overlay_pnl": summary.get("overlay_total_pnl_pct"),
            "delta": summary.get("overlay_delta_pnl_pct"),
            "quality_label": quality_label,
            "market_data_stale": health_summary.get("market_data_stale"),
            "last_market_candle_date": health_summary.get("last_market_candle_date"),
        },
        "recommended_action": health.get("recommended_action") if health_summary.get("market_data_stale") else summary.get("recommended_action"),
        "warnings": sorted(set((report.get("warnings") or []) + (health.get("warnings") or []))),
    }


def build_data_health_warnings(summary: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if not summary.get("last_market_candle_date"):
        warnings.append("stale_market_data")
    elif summary.get("market_data_stale"):
        warnings.append("stale_market_data")
    if int(summary.get("total_snapshots") or 0) <= 0:
        warnings.append("no_snapshots")
    if int(summary.get("ready_snapshots") or 0) <= 0:
        warnings.append("no_ready_snapshots")
    if int(summary.get("open_snapshots") or 0) > 10:
        warnings.append("too_many_open_snapshots")
    if int(summary.get("event_count") or 0) <= 0:
        warnings.append("event_coverage_missing")
    if int(summary.get("ready_with_missing_future_candles") or 0) > 0:
        warnings.append("future_candles_missing_for_ready_snapshots")
    return warnings


def build_conservative_overlay_data_health(
    db: Session,
    *,
    stale_days: int = 3,
) -> dict[str, Any]:
    _ensure_tables(db)
    today = date.today()
    last_candle_date = db.scalar(select(func.max(Candle.trade_date)))
    event_count = int(db.scalar(select(func.count(MarketEvent.id))) or 0)
    lifecycle = build_event_overlay_paper_lifecycle_status(db)
    lifecycle_summary = lifecycle.get("summary") or {}
    ready = get_ready_to_evaluate_snapshots(db, limit=100)
    ready_missing = 0
    for snapshot in ready.get("snapshots") or []:
        snapshot_date = _date_or_none(snapshot.get("snapshot_date"))
        horizon_days = int(snapshot.get("horizon_days") or 0)
        if snapshot_date and last_candle_date and last_candle_date < snapshot_date + timedelta(days=horizon_days):
            ready_missing += 1
    days_since_candle = (today - last_candle_date).days if last_candle_date else None
    summary = {
        "last_market_candle_date": last_candle_date.isoformat() if last_candle_date else None,
        "days_since_last_market_candle": days_since_candle,
        "market_data_stale": bool(days_since_candle is None or days_since_candle > stale_days),
        "total_snapshots": lifecycle_summary.get("total_snapshots", 0),
        "open_snapshots": lifecycle_summary.get("open_snapshots", 0),
        "ready_snapshots": ready.get("ready_count", 0),
        "evaluated_snapshots": lifecycle_summary.get("evaluated_snapshots", 0),
        "last_snapshot_date": lifecycle_summary.get("last_snapshot_date"),
        "days_since_last_snapshot": lifecycle_summary.get("days_since_last_snapshot"),
        "event_count": event_count,
        "ready_with_missing_future_candles": ready_missing,
    }
    warnings = build_data_health_warnings(summary)
    if "stale_market_data" in warnings:
        recommended_action = "bootstrap_data" if not summary.get("last_market_candle_date") else "refresh_market_data"
    elif "no_snapshots" in warnings:
        recommended_action = "create_snapshot"
    elif int(summary.get("ready_snapshots") or 0) > 0:
        recommended_action = "evaluate_ready"
    elif int(summary.get("open_snapshots") or 0) > 0:
        recommended_action = "wait"
    else:
        recommended_action = "review"
    return {
        "ok": True,
        "mode": "conservative_overlay_data_health",
        "summary": summary,
        "warnings": warnings,
        "recommended_action": recommended_action,
    }


def run_conservative_overlay_daily_report(
    db: Session,
    *,
    name: str = "daily",
    limit: int = 100,
    candles_limit: int = 240,
    horizon_days: int = 20,
    evaluate_ready: bool = True,
    dedupe_same_day: bool = True,
) -> dict[str, Any]:
    daily = create_conservative_overlay_paper_snapshot(
        db,
        name=name,
        limit=limit,
        candles_limit=candles_limit,
        horizon_days=horizon_days,
        overlay_mode="soft_adjust",
        dedupe_same_day=dedupe_same_day,
    )
    eval_result = (
        bulk_evaluate_ready_snapshots(db, limit=50)
        if evaluate_ready
        else {"ok": True, "evaluated_snapshots": 0, "total_insufficient_data": 0}
    )
    report = build_conservative_overlay_quality_report(db, limit=30)
    return {
        "ok": bool(daily.get("ok")) and bool(eval_result.get("ok")),
        "mode": "daily_run",
        "created_snapshot": bool(daily.get("created")),
        "snapshot_id": daily.get("snapshot_id"),
        "duplicate": bool(daily.get("duplicate")),
        "evaluated_ready": bool(evaluate_ready),
        "evaluated_snapshots": int(eval_result.get("evaluated_snapshots") or 0),
        "insufficient_data": int(eval_result.get("total_insufficient_data") or 0),
        "dashboard_summary": report.get("summary") or {},
        "warnings": sorted(set((report.get("warnings") or []) + (["daily_snapshot_already_exists"] if daily.get("duplicate") else []))),
        "recommended_next_action": (report.get("summary") or {}).get("recommended_action"),
    }


def build_conservative_overlay_quality_report_csv(
    db: Session,
    *,
    limit: int = 30,
) -> str:
    data = build_conservative_overlay_quality_report(db, limit=limit, include_open_snapshots=True)
    rows: list[dict[str, Any]] = []
    for key, value in (data.get("summary") or {}).items():
        if not isinstance(value, (dict, list)):
            rows.append({"section": "summary", "metric": key, "value": value})
    for row in data.get("by_risk_level") or []:
        level = row.get("risk_level")
        for key, value in row.items():
            if key != "risk_level":
                rows.append({"section": f"risk_level:{level}", "metric": key, "value": value})
    for row in data.get("recent_snapshots") or []:
        rows.append({"section": "recent_snapshot", "metric": row.get("id"), "value": row.get("status")})
    for row in data.get("top_positive_contributors") or []:
        rows.append({"section": "top_positive", "metric": row.get("ticker"), "value": row.get("overlay_delta_pnl_pct")})
    for row in data.get("top_negative_contributors") or []:
        rows.append({"section": "top_negative", "metric": row.get("ticker"), "value": row.get("overlay_delta_pnl_pct")})
    return _csv_text(["section", "metric", "value"], rows)
