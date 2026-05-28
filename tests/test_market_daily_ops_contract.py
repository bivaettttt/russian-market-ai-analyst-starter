from app.services import market_daily_ops as ops


def test_market_daily_ops_contract_imports():
    assert callable(ops.build_daily_ops_status)
    assert callable(ops.run_market_daily_ops)


def test_market_daily_ops_dry_run_skips_writes(monkeypatch):
    monkeypatch.setattr(
        ops,
        "build_daily_ops_status",
        lambda *_args, **_kwargs: {
            "ok": True,
            "summary": {},
            "warnings": [],
        },
    )
    monkeypatch.setattr(
        ops,
        "refresh_market_data_daily",
        lambda *_args, **_kwargs: {
            "ok": True,
            "recommendation": "dry_run_only",
            "warnings": [],
        },
    )
    monkeypatch.setattr(
        ops,
        "build_market_data_freshness_status",
        lambda *_args, **_kwargs: {
            "ok": True,
            "summary": {
                "latest_candle_date": "2026-05-28",
                "is_stale": False,
            },
            "warnings": [],
        },
    )
    monkeypatch.setattr(
        ops,
        "create_conservative_overlay_paper_snapshot",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("snapshot create should not run")),
    )
    monkeypatch.setattr(
        ops,
        "bulk_evaluate_ready_snapshots",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("evaluate should not run")),
    )
    monkeypatch.setattr(
        ops,
        "build_conservative_overlay_quality_report",
        lambda *_args, **_kwargs: {
            "summary": {"quality_label": "insufficient_data"},
            "warnings": [],
        },
    )
    monkeypatch.setattr(
        ops,
        "build_conservative_overlay_notification_summary",
        lambda *_args, **_kwargs: {"warnings": []},
    )
    monkeypatch.setattr(
        ops,
        "build_conservative_overlay_data_health",
        lambda *_args, **_kwargs: {
            "summary": {"ready_snapshots": 0},
            "warnings": [],
        },
    )

    result = ops.run_market_daily_ops(object(), dry_run=True)

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["summary"]["created_snapshot"] is False
    assert result["summary"]["evaluated_snapshots"] == 0
