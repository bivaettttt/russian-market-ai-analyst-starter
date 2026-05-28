from app.services import event_overlay_paper_tracking as tracking


def test_event_overlay_paper_tracking_contract_imports():
    assert callable(tracking.create_conservative_overlay_paper_snapshot)
    assert callable(tracking.list_event_overlay_paper_snapshots)
    assert callable(tracking.get_event_overlay_paper_snapshot_detail)
    assert callable(tracking.evaluate_event_overlay_paper_snapshot)
    assert callable(tracking.build_event_overlay_paper_dashboard)


def test_dashboard_empty_state_with_monkeypatched_tables(monkeypatch):
    class _Result:
        def all(self):
            return []

    class _DB:
        def scalars(self, *_args, **_kwargs):
            return _Result()

    monkeypatch.setattr(tracking, "_ensure_tables", lambda _db: None)

    data = tracking.build_event_overlay_paper_dashboard(_DB(), limit=5)

    assert data["ok"] is True
    assert data["summary"]["snapshots"] == 0
    assert data["summary"]["aggregate_overlay_delta_pnl_pct"] == 0.0
