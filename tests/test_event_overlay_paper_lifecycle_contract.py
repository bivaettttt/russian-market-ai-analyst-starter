from app.services import event_overlay_paper_tracking as tracking


def test_lifecycle_contract_imports():
    assert callable(tracking.get_ready_to_evaluate_snapshots)
    assert callable(tracking.bulk_evaluate_ready_snapshots)
    assert callable(tracking.build_event_overlay_paper_lifecycle_status)
    assert callable(tracking.delete_event_overlay_paper_snapshot)
    assert callable(tracking.build_event_overlay_paper_dashboard)
