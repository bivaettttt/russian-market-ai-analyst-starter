from app.services import event_overlay_paper_tracking as tracking


def test_daily_run_contract_imports():
    assert callable(tracking.run_conservative_overlay_daily_workflow)


def test_daily_run_dedupe_summary(monkeypatch):
    monkeypatch.setattr(
        tracking,
        "build_event_overlay_paper_lifecycle_status",
        lambda *_args, **_kwargs: {
            "summary": {
                "recommended_action": "wait",
            }
        },
    )
    monkeypatch.setattr(
        tracking,
        "create_conservative_overlay_paper_snapshot",
        lambda *_args, **_kwargs: {
            "ok": True,
            "created": False,
            "duplicate": True,
            "snapshot_id": 7,
        },
    )
    monkeypatch.setattr(
        tracking,
        "bulk_evaluate_ready_snapshots",
        lambda *_args, **_kwargs: {
            "ok": True,
            "evaluated_snapshots": 2,
            "total_insufficient_data": 1,
        },
    )
    monkeypatch.setattr(
        tracking,
        "build_event_overlay_paper_dashboard",
        lambda *_args, **_kwargs: {
            "summary": {
                "evaluated_items": 3,
                "overlay_delta_pnl_pct": 0.1,
            }
        },
    )

    result = tracking.run_conservative_overlay_daily_workflow(object(), name="daily")

    assert result["ok"] is True
    assert result["duplicate"] is True
    assert result["snapshot_id"] == 7
    assert result["evaluated_snapshots"] == 2
    assert "daily_snapshot_already_exists" in result["warnings"]
