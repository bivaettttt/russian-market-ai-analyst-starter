from app.services import market_data_refresh as refresh


def test_market_data_refresh_contract_imports():
    assert callable(refresh.build_market_data_freshness_status)
    assert callable(refresh.refresh_market_data_daily)


def test_freshness_recommendation_helper():
    assert (
        refresh._freshness_recommendation(
            tickers_with_candles=0,
            total_instruments=0,
            is_stale=True,
        )
        == "bootstrap_required"
    )
    assert (
        refresh._freshness_recommendation(
            tickers_with_candles=10,
            total_instruments=10,
            is_stale=True,
        )
        == "refresh_market_data"
    )
    assert (
        refresh._freshness_recommendation(
            tickers_with_candles=10,
            total_instruments=10,
            is_stale=False,
        )
        == "fresh"
    )


def test_refresh_dry_run_does_not_call_bootstrap(monkeypatch):
    monkeypatch.setattr(
        refresh,
        "build_market_data_freshness_status",
        lambda *_args, **_kwargs: {
            "ok": True,
            "summary": {
                "is_stale": True,
                "tickers_with_candles": 5,
            },
            "warnings": ["stale_market_data"],
        },
    )
    monkeypatch.setattr(
        refresh,
        "bootstrap_moex_universe",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("network helper should not run")),
    )
    monkeypatch.setattr(
        refresh,
        "_latest_candle_dates_by_ticker",
        lambda *_args, **_kwargs: {"SBER": "2026-05-21"},
    )

    result = refresh.refresh_market_data_daily(object(), dry_run=True)

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["refresh_result"]["would_refresh"] is True
