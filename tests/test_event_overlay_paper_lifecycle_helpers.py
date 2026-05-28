from app.services.event_overlay_paper_tracking import (
    is_snapshot_ready_to_evaluate,
    recommend_lifecycle_action,
)


def test_ready_to_evaluate_respects_horizon_and_status():
    snapshot = {
        "snapshot_date": "2026-01-01",
        "horizon_days": 20,
        "status": "open",
    }
    assert is_snapshot_ready_to_evaluate(snapshot, as_of_date="2026-01-20") is False
    assert is_snapshot_ready_to_evaluate(snapshot, as_of_date="2026-01-21") is True

    snapshot["status"] = "evaluated"
    assert is_snapshot_ready_to_evaluate(snapshot, as_of_date="2026-02-01") is False


def test_lifecycle_recommendation():
    assert recommend_lifecycle_action(total_snapshots=0, ready_count=0, days_since_last_snapshot=None) == "create_snapshot"
    assert recommend_lifecycle_action(total_snapshots=2, ready_count=1, days_since_last_snapshot=1) == "evaluate_ready"
    assert recommend_lifecycle_action(total_snapshots=2, ready_count=0, days_since_last_snapshot=2) == "wait"
    assert recommend_lifecycle_action(total_snapshots=2, ready_count=0, days_since_last_snapshot=8) == "create_snapshot"
