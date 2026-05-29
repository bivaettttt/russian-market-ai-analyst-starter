from app.services.event_overlay_paper_tracking import filter_paper_snapshots
from app.services.event_overlay_quality_report import classify_overlay_quality


def _snapshot(name, baseline=10.0, overlay=9.0, summary=None):
    return {
        "name": name,
        "source": "conservative_event_overlay",
        "snapshot_date": "2026-05-29",
        "horizon_days": 20,
        "baseline_total_exposure": baseline,
        "overlay_total_exposure": overlay,
        "summary": summary or {"position_size_source": "fallback_default"},
    }


def test_official_only_filter_keeps_only_official_snapshots():
    snapshots = [
        _snapshot("official-daily-2026-05-29"),
        _snapshot("manual-daily"),
        _snapshot("exposure-fix-test"),
        _snapshot("old-zero", baseline=0.0, overlay=0.0),
    ]

    filtered = filter_paper_snapshots(snapshots, official_only=True)

    assert [row["name"] for row in filtered] == ["official-daily-2026-05-29"]


def test_include_legacy_false_removes_zero_exposure_snapshots():
    snapshots = [
        _snapshot("manual-daily"),
        _snapshot("legacy-zero", baseline=0.0, overlay=0.0),
    ]

    filtered = filter_paper_snapshots(snapshots, include_legacy=False)

    assert [row["name"] for row in filtered] == ["manual-daily"]


def test_include_test_false_removes_test_snapshots():
    snapshots = [
        _snapshot("manual-daily"),
        _snapshot("manual-test"),
    ]

    filtered = filter_paper_snapshots(snapshots, include_test=False)

    assert [row["name"] for row in filtered] == ["manual-daily"]


def test_quality_label_helper_still_classifies_overlay_delta():
    assert classify_overlay_quality(evaluated_items=0, overlay_delta_pnl_pct=0.0) == "insufficient_data"
    assert classify_overlay_quality(evaluated_items=12, overlay_delta_pnl_pct=0.2) == "improving"
    assert classify_overlay_quality(evaluated_items=12, overlay_delta_pnl_pct=-0.2) == "underperforming"
