from app.services import market_daily_ops as ops


def test_daily_ops_passes_refresh_hardening_params(monkeypatch):
    captured = {}

    monkeypatch.setattr(ops, "build_daily_ops_status", lambda *_args, **_kwargs: {"ok": True, "summary": {}, "warnings": []})

    def _refresh(*_args, **kwargs):
        captured.update(kwargs)
        return {"ok": True, "recommendation": "partial_refresh", "warnings": []}

    monkeypatch.setattr(ops, "refresh_market_data_daily", _refresh)
    monkeypatch.setattr(
        ops,
        "build_market_data_freshness_status",
        lambda *_args, **_kwargs: {"ok": True, "summary": {"is_stale": False, "latest_candle_date": "2026-05-28"}, "warnings": []},
    )
    monkeypatch.setattr(
        ops,
        "create_conservative_overlay_paper_snapshot",
        lambda *_args, **_kwargs: {"ok": True, "created": True, "duplicate": False, "snapshot_id": 1, "warnings": []},
    )
    monkeypatch.setattr(
        ops,
        "bulk_evaluate_ready_snapshots",
        lambda *_args, **_kwargs: {"ok": True, "evaluated_snapshots": 0, "total_evaluated_items": 0, "total_insufficient_data": 0},
    )
    monkeypatch.setattr(
        ops,
        "build_conservative_overlay_quality_report",
        lambda *_args, **_kwargs: {"summary": {"quality_label": "insufficient_data"}, "warnings": []},
    )
    monkeypatch.setattr(ops, "build_conservative_overlay_notification_summary", lambda *_args, **_kwargs: {"warnings": []})
    monkeypatch.setattr(ops, "build_conservative_overlay_data_health", lambda *_args, **_kwargs: {"summary": {"ready_snapshots": 0}, "warnings": []})

    result = ops.run_market_daily_ops(
        object(),
        request_timeout=4,
        max_retries=0,
        retry_backoff=0,
        refresh_universe=False,
        fallback_to_existing_universe=False,
        continue_on_error=False,
        max_runtime_seconds=30,
    )

    assert result["ok"] is True
    assert captured["request_timeout"] == 4
    assert captured["max_retries"] == 0
    assert captured["refresh_universe"] is False
    assert captured["fallback_to_existing_universe"] is False
    assert captured["continue_on_error"] is False
    assert captured["max_runtime_seconds"] == 30
