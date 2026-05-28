from app.services.event_overlay_paper_snapshot import build_event_overlay_paper_snapshot


def test_event_overlay_paper_snapshot_contract_imports():
    assert callable(build_event_overlay_paper_snapshot)
