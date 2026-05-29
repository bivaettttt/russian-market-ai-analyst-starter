from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.services.event_overlay_paper_tracking import (
    build_official_live_validation_summary,
    build_event_overlay_paper_lifecycle_status,
    bulk_evaluate_ready_snapshots,
    create_conservative_overlay_paper_snapshot,
)
from app.services.event_overlay_quality_report import (
    build_conservative_overlay_notification_summary,
    build_conservative_overlay_quality_report,
)
from app.services.market_data_refresh import build_market_data_freshness_status, refresh_market_data_daily
from app.services.market_refresh_report import build_market_refresh_notification


def should_block_live_validation_start(
    *,
    require_fresh_market_data: bool,
    market_freshness: dict[str, Any],
) -> tuple[bool, str | None]:
    if not require_fresh_market_data:
        return False, None
    summary = market_freshness.get("summary") or {}
    if int(summary.get("tickers_with_candles") or 0) <= 0:
        return True, "no_market_data"
    if bool(summary.get("is_stale")):
        return True, "market_data_stale"
    return False, None


def build_live_paper_validation_status(
    db: Session,
    *,
    max_stale_days: int = 3,
) -> dict[str, Any]:
    market_notification = build_market_refresh_notification(db, stale_days=max_stale_days)
    market_freshness = build_market_data_freshness_status(db, stale_days=max_stale_days)
    paper_lifecycle = build_event_overlay_paper_lifecycle_status(db)
    quality_report = build_conservative_overlay_quality_report(
        db,
        limit=30,
        official_only=True,
        include_test=False,
        include_legacy=False,
    )
    official_summary = build_official_live_validation_summary(db)
    blocked, blocked_reason = should_block_live_validation_start(
        require_fresh_market_data=True,
        market_freshness=market_freshness,
    )
    return {
        "ok": True,
        "mode": "live_paper_validation_status",
        "summary": {
            "blocked": blocked,
            "blocked_reason": blocked_reason,
            "latest_candle_date": (market_freshness.get("summary") or {}).get("latest_candle_date"),
            "market_data_stale": (market_freshness.get("summary") or {}).get("is_stale"),
            "paper_snapshots_total": (paper_lifecycle.get("summary") or {}).get("total_snapshots"),
            "ready_to_evaluate": (paper_lifecycle.get("summary") or {}).get("ready_to_evaluate_snapshots"),
            "quality_label": (quality_report.get("summary") or {}).get("quality_label"),
            "has_official_snapshot": (official_summary.get("summary") or {}).get("has_official_snapshot"),
            "latest_official_snapshot_id": (official_summary.get("summary") or {}).get("latest_official_snapshot_id"),
            "latest_official_snapshot_date": (official_summary.get("summary") or {}).get("latest_official_snapshot_date"),
            "next_evaluation_date": (official_summary.get("summary") or {}).get("next_evaluation_date"),
            "days_until_next_evaluation": (official_summary.get("summary") or {}).get("days_until_next_evaluation"),
        },
        "market_notification": market_notification,
        "market_freshness": market_freshness,
        "paper_lifecycle": paper_lifecycle,
        "quality_report": quality_report,
        "official_summary": official_summary,
        "warnings": sorted(set((market_notification.get("warnings") or []) + (quality_report.get("warnings") or []))),
    }


def start_live_paper_validation_run(
    db: Session,
    *,
    name: str = "official-daily",
    limit: int = 100,
    horizon_days: int = 20,
    refresh_market_data: bool = True,
    refresh_max_tickers: int = 150,
    refresh_days: int = 120,
    require_fresh_market_data: bool = True,
    max_stale_days: int = 3,
    evaluate_ready: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    pre_freshness = build_market_data_freshness_status(db, stale_days=max_stale_days)
    market_refresh: dict[str, Any] = {
        "ok": True,
        "mode": "market_data_daily_refresh",
        "disabled": True,
        "dry_run": dry_run,
        "before": pre_freshness,
        "after": pre_freshness,
        "warnings": pre_freshness.get("warnings") or [],
        "recommendation": "disabled",
    }
    if refresh_market_data:
        market_refresh = refresh_market_data_daily(
            db,
            max_tickers=refresh_max_tickers,
            days=refresh_days,
            dry_run=dry_run,
            force=False,
        )
    post_freshness = build_market_data_freshness_status(db, stale_days=max_stale_days)
    blocked, blocked_reason = should_block_live_validation_start(
        require_fresh_market_data=require_fresh_market_data,
        market_freshness=post_freshness,
    )
    warnings = sorted(set((market_refresh.get("warnings") or []) + (post_freshness.get("warnings") or [])))
    if blocked:
        return {
            "ok": False,
            "mode": "live_paper_validation_start",
            "status": "blocked",
            "created_snapshot": False,
            "snapshot_id": None,
            "blocked_reason": blocked_reason,
            "market_refresh": market_refresh,
            "market_freshness": post_freshness,
            "paper_tracking": None,
            "quality_report": build_conservative_overlay_quality_report(db, limit=30, official_only=True, include_test=False, include_legacy=False),
            "notification": build_conservative_overlay_notification_summary(db, limit=30, official_only=True, include_test=False, include_legacy=False),
            "warnings": sorted(set(warnings + [str(blocked_reason)])),
            "next_steps": ["refresh_market_data", "verify_market_freshness", "rerun_live_paper_validation_start"],
        }
    if dry_run:
        return {
            "ok": True,
            "mode": "live_paper_validation_start",
            "status": "dry_run",
            "created_snapshot": False,
            "snapshot_id": None,
            "blocked_reason": None,
            "market_refresh": market_refresh,
            "market_freshness": post_freshness,
            "paper_tracking": {"planned": True, "name": f"{name}-{date.today().isoformat()}", "limit": limit, "horizon_days": horizon_days},
            "quality_report": build_conservative_overlay_quality_report(db, limit=30, official_only=True, include_test=False, include_legacy=False),
            "notification": build_conservative_overlay_notification_summary(db, limit=30, official_only=True, include_test=False, include_legacy=False),
            "warnings": warnings,
            "next_steps": ["run_without_dry_run_after_review"],
        }

    official_name = f"{name}-{date.today().isoformat()}"
    snapshot = create_conservative_overlay_paper_snapshot(
        db,
        name=official_name,
        limit=limit,
        candles_limit=240,
        horizon_days=horizon_days,
        overlay_mode="soft_adjust",
        dedupe_same_day=True,
    )
    evaluate_result = (
        bulk_evaluate_ready_snapshots(db, limit=50, official_only=True, include_test=False, include_legacy=False)
        if evaluate_ready
        else {"ok": True, "mode": "bulk_evaluate_ready_snapshots", "evaluated_snapshots": 0, "warnings": ["evaluate_ready_disabled"]}
    )
    quality = build_conservative_overlay_quality_report(db, limit=30, official_only=True, include_test=False, include_legacy=False)
    notification = build_conservative_overlay_notification_summary(db, limit=30, official_only=True, include_test=False, include_legacy=False)
    degraded = bool((post_freshness.get("summary") or {}).get("is_stale"))
    return {
        "ok": bool(snapshot.get("ok")) and bool(evaluate_result.get("ok")),
        "mode": "live_paper_validation_start",
        "status": "degraded" if degraded else "completed",
        "created_snapshot": bool(snapshot.get("created")),
        "snapshot_id": snapshot.get("snapshot_id"),
        "blocked_reason": None,
        "market_refresh": market_refresh,
        "market_freshness": post_freshness,
        "paper_tracking": {"snapshot": snapshot, "evaluate_ready": evaluate_result},
        "quality_report": quality,
        "official_summary": build_official_live_validation_summary(db),
        "notification": notification,
        "warnings": sorted(set(warnings + (snapshot.get("warnings") or []) + (evaluate_result.get("warnings") or []) + (quality.get("warnings") or []))),
        "next_steps": ["review_quality_report", "evaluate_ready_after_horizon"],
    }
