import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models import EventOverlayPaperSnapshot, EventOverlayPaperSnapshotItem
from app.services.event_overlay_paper_tracking import cleanup_event_overlay_paper_snapshots


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    EventOverlayPaperSnapshot.__table__.create(bind=engine, checkfirst=True)
    EventOverlayPaperSnapshotItem.__table__.create(bind=engine, checkfirst=True)
    return sessionmaker(bind=engine)()


def _add_snapshot(db, *, name, baseline, overlay, summary=None):
    row = EventOverlayPaperSnapshot(
        snapshot_date="2026-05-29",
        name=name,
        source="conservative_event_overlay",
        config_id="cons_t20_40_60_80_m95_e80_h65_x40_w100",
        overlay_mode="soft_adjust",
        limit=10,
        candles_limit=240,
        horizon_days=20,
        baseline_total_exposure=baseline,
        overlay_total_exposure=overlay,
        exposure_reduction_pct=0.0,
        avg_multiplier=1.0,
        risk_level_counts_json="{}",
        summary_json=json.dumps(summary or {"position_size_source": "fallback_default"}),
        status="open",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_cleanup_dry_run_finds_candidates_without_deleting():
    db = _session()
    try:
        official = _add_snapshot(db, name="official-daily-2026-05-29", baseline=10.0, overlay=9.0)
        legacy = _add_snapshot(db, name="legacy-zero", baseline=0.0, overlay=0.0)
        test = _add_snapshot(db, name="manual-test", baseline=10.0, overlay=9.0)

        result = cleanup_event_overlay_paper_snapshots(
            db,
            delete_legacy_zero_exposure=True,
            delete_test_snapshots=True,
            keep_official=True,
            dry_run=True,
        )

        candidate_ids = {row["id"] for row in result["candidates"]}
        remaining_ids = set(db.scalars(select(EventOverlayPaperSnapshot.id)).all())
        assert result["dry_run"] is True
        assert candidate_ids == {legacy.id, test.id}
        assert official.id in remaining_ids
        assert legacy.id in remaining_ids
        assert test.id in remaining_ids
    finally:
        db.close()


def test_cleanup_delete_keeps_official_by_default():
    db = _session()
    try:
        official = _add_snapshot(db, name="official-daily-2026-05-29", baseline=10.0, overlay=9.0)
        legacy = _add_snapshot(db, name="legacy-zero", baseline=0.0, overlay=0.0)

        result = cleanup_event_overlay_paper_snapshots(
            db,
            delete_legacy_zero_exposure=True,
            keep_official=True,
            dry_run=False,
        )

        remaining_ids = set(db.scalars(select(EventOverlayPaperSnapshot.id)).all())
        assert result["deleted_snapshots"] == 1
        assert official.id in remaining_ids
        assert legacy.id not in remaining_ids
    finally:
        db.close()
