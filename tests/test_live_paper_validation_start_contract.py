from app.services import live_paper_validation_start as live


def test_live_paper_validation_contract_imports():
    assert callable(live.build_live_paper_validation_status)
    assert callable(live.start_live_paper_validation_run)


def test_live_paper_validation_dry_run_does_not_create(monkeypatch):
    monkeypatch.setattr(
        live,
        "build_market_data_freshness_status",
        lambda *_args, **_kwargs: {
            "summary": {
                "tickers_with_candles": 5,
                "is_stale": False,
                "latest_candle_date": "2026-05-28",
            },
            "warnings": [],
        },
    )
    monkeypatch.setattr(
        live,
        "create_conservative_overlay_paper_snapshot",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("snapshot create should not run")),
    )
    monkeypatch.setattr(
        live,
        "bulk_evaluate_ready_snapshots",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("evaluate should not run")),
    )
    monkeypatch.setattr(live, "build_conservative_overlay_quality_report", lambda *_args, **_kwargs: {"warnings": []})
    monkeypatch.setattr(live, "build_conservative_overlay_notification_summary", lambda *_args, **_kwargs: {"warnings": []})

    result = live.start_live_paper_validation_run(
        object(),
        refresh_market_data=False,
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["status"] == "dry_run"
    assert result["created_snapshot"] is False


def test_live_paper_validation_blocks_before_create(monkeypatch):
    monkeypatch.setattr(
        live,
        "build_market_data_freshness_status",
        lambda *_args, **_kwargs: {
            "summary": {
                "tickers_with_candles": 5,
                "is_stale": True,
                "latest_candle_date": "2026-05-21",
            },
            "warnings": ["stale_market_data"],
        },
    )
    monkeypatch.setattr(
        live,
        "create_conservative_overlay_paper_snapshot",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("snapshot create should not run")),
    )
    monkeypatch.setattr(live, "build_conservative_overlay_quality_report", lambda *_args, **_kwargs: {"warnings": []})
    monkeypatch.setattr(live, "build_conservative_overlay_notification_summary", lambda *_args, **_kwargs: {"warnings": []})

    result = live.start_live_paper_validation_run(
        object(),
        refresh_market_data=False,
        require_fresh_market_data=True,
    )

    assert result["ok"] is False
    assert result["status"] == "blocked"
    assert result["blocked_reason"] == "market_data_stale"
    assert "refresh_market_data" in result["next_steps"]
