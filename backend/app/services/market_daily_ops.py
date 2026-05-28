from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.event_overlay_paper_tracking import (
    build_event_overlay_paper_lifecycle_status,
    bulk_evaluate_ready_snapshots,
    create_conservative_overlay_paper_snapshot,
)
from app.services.event_overlay_quality_report import (
    build_conservative_overlay_data_health,
    build_conservative_overlay_notification_summary,
    build_conservative_overlay_quality_report,
)
from app.services.market_data_refresh import build_market_data_freshness_status, refresh_market_data_daily


def select_daily_ops_recommended_action(
    *,
    market_data_stale: bool,
    ready_snapshots: int,
    created_snapshot: bool,
    duplicate_snapshot: bool,
    quality_label: str | None,
) -> str:
    if market_data_stale:
        return "refresh_market_data"
    if ready_snapshots > 0:
        return "evaluate_ready"
    if created_snapshot:
        return "review_dashboard"
    if not duplicate_snapshot:
        return "create_snapshot"
    if quality_label == "underperforming":
        return "review_underperformance"
    return "continue_tracking"


def merge_daily_ops_warnings(*parts: dict[str, Any] | None) -> list[str]:
    warnings: list[str] = []
    for part in parts:
        if not part:
            continue
        warnings.extend(str(item) for item in (part.get("warnings") or []) if item)
        summary = part.get("summary") or {}
        if summary.get("market_data_stale") or summary.get("is_stale"):
            warnings.append("stale_market_data")
    return sorted(set(warnings))


def build_daily_ops_status(
    db: Session,
    *,
    stale_days: int = 3,
) -> dict[str, Any]:
    market = build_market_data_freshness_status(db, stale_days=stale_days)
    lifecycle = build_event_overlay_paper_lifecycle_status(db)
    notification = build_conservative_overlay_notification_summary(db)
    data_health = build_conservative_overlay_data_health(db, stale_days=stale_days)
    warnings = merge_daily_ops_warnings(market, lifecycle, notification, data_health)
    market_summary = market.get("summary") or {}
    lifecycle_summary = lifecycle.get("summary") or {}
    notification_metrics = notification.get("metrics") or {}
    recommended_action = data_health.get("recommended_action") or notification.get("recommended_action")
    return {
        "ok": True,
        "mode": "market_daily_ops_status",
        "summary": {
            "latest_candle_date": market_summary.get("latest_candle_date"),
            "market_data_stale": market_summary.get("is_stale"),
            "paper_snapshots_total": lifecycle_summary.get("total_snapshots"),
            "ready_to_evaluate": lifecycle_summary.get("ready_to_evaluate_snapshots"),
            "quality_label": notification_metrics.get("quality_label"),
            "recommended_action": recommended_action,
        },
        "market_freshness": market,
        "paper_lifecycle": lifecycle,
        "notification": notification,
        "data_health": data_health,
        "warnings": warnings,
        "recommended_action": recommended_action,
    }


def _disabled_market_refresh(db: Session) -> dict[str, Any]:
    status = build_market_data_freshness_status(db)
    return {
        "ok": True,
        "mode": "market_data_daily_refresh",
        "disabled": True,
        "dry_run": False,
        "before": status,
        "after": status,
        "refresh_result": {"skipped_reason": "disabled"},
        "warnings": status.get("warnings") or [],
        "recommendation": "disabled",
    }


def run_market_daily_ops(
    db: Session,
    *,
    name: str = "daily",
    limit: int = 100,
    candles_limit: int = 240,
    horizon_days: int = 20,
    refresh_market_data: bool = True,
    refresh_max_tickers: int = 150,
    refresh_days: int = 120,
    evaluate_ready: bool = True,
    dedupe_same_day: bool = True,
    dry_run: bool = False,
    force_refresh: bool = False,
) -> dict[str, Any]:
    preflight = build_daily_ops_status(db)
    market_refresh = (
        refresh_market_data_daily(
            db,
            max_tickers=refresh_max_tickers,
            days=refresh_days,
            dry_run=dry_run,
            force=force_refresh,
        )
        if refresh_market_data
        else _disabled_market_refresh(db)
    )
    post_freshness = build_market_data_freshness_status(db)
    paper_snapshot: dict[str, Any]
    evaluate_result: dict[str, Any]
    if dry_run:
        paper_snapshot = {
            "ok": True,
            "mode": "create_conservative_overlay_paper_snapshot",
            "planned": True,
            "created": False,
            "duplicate": False,
            "snapshot_id": None,
        }
        evaluate_result = {
            "ok": True,
            "mode": "bulk_evaluate_ready_snapshots",
            "planned": bool(evaluate_ready),
            "evaluated_snapshots": 0,
            "total_evaluated_items": 0,
            "total_insufficient_data": 0,
        }
    else:
        paper_snapshot = create_conservative_overlay_paper_snapshot(
            db,
            name=name,
            limit=limit,
            candles_limit=candles_limit,
            horizon_days=horizon_days,
            overlay_mode="soft_adjust",
            dedupe_same_day=dedupe_same_day,
        )
        evaluate_result = (
            bulk_evaluate_ready_snapshots(db, limit=50)
            if evaluate_ready
            else {
                "ok": True,
                "mode": "bulk_evaluate_ready_snapshots",
                "evaluated_snapshots": 0,
                "total_evaluated_items": 0,
                "total_insufficient_data": 0,
                "warnings": ["evaluate_ready_disabled"],
            }
        )

    quality_report = build_conservative_overlay_quality_report(db, limit=30)
    notification = build_conservative_overlay_notification_summary(db, limit=30)
    data_health = build_conservative_overlay_data_health(db)
    warnings = merge_daily_ops_warnings(market_refresh, post_freshness, paper_snapshot, evaluate_result, quality_report, notification, data_health)
    post_summary = post_freshness.get("summary") or {}
    quality_summary = quality_report.get("summary") or {}
    ready_count = int((data_health.get("summary") or {}).get("ready_snapshots") or 0)
    recommended_action = select_daily_ops_recommended_action(
        market_data_stale=bool(post_summary.get("is_stale")),
        ready_snapshots=ready_count,
        created_snapshot=bool(paper_snapshot.get("created")),
        duplicate_snapshot=bool(paper_snapshot.get("duplicate")),
        quality_label=quality_summary.get("quality_label"),
    )
    errors = []
    errors.extend(str(item) for item in market_refresh.get("errors", []) if item)
    if not paper_snapshot.get("ok"):
        errors.append(str(paper_snapshot.get("error") or "paper_snapshot_failed"))
    if not evaluate_result.get("ok"):
        errors.append(str(evaluate_result.get("error") or "evaluate_ready_failed"))
    market_status = "disabled"
    if refresh_market_data:
        if dry_run:
            market_status = "dry_run"
        elif market_refresh.get("recommendation") == "market_data_fresh":
            market_status = "skipped"
        elif market_refresh.get("ok"):
            market_status = "completed"
        else:
            market_status = "failed"
    return {
        "ok": len(errors) == 0,
        "mode": "market_daily_ops",
        "dry_run": dry_run,
        "steps": {
            "preflight": preflight,
            "market_refresh": market_refresh,
            "paper_snapshot": paper_snapshot,
            "evaluate_ready": evaluate_result,
            "quality_report": quality_report,
            "notification": notification,
            "data_health": data_health,
        },
        "summary": {
            "market_refresh_status": market_status,
            "latest_candle_date": post_summary.get("latest_candle_date"),
            "market_data_stale": post_summary.get("is_stale"),
            "created_snapshot": bool(paper_snapshot.get("created")),
            "snapshot_id": paper_snapshot.get("snapshot_id"),
            "duplicate_snapshot": bool(paper_snapshot.get("duplicate")),
            "evaluated_snapshots": int(evaluate_result.get("evaluated_snapshots") or 0),
            "evaluated_items": int(evaluate_result.get("total_evaluated_items") or 0),
            "insufficient_data": int(evaluate_result.get("total_insufficient_data") or 0),
            "quality_label": quality_summary.get("quality_label"),
            "recommended_action": recommended_action,
            "warnings_count": len(warnings),
        },
        "warnings": warnings,
        "errors": errors,
        "recommended_action": recommended_action,
    }
