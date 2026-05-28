from app.services import market_data_refresh as refresh


def _freshness(is_stale=True):
    return {
        "ok": True,
        "summary": {
            "is_stale": is_stale,
            "tickers_with_candles": 3,
            "latest_candle_date": "2026-05-21",
        },
        "warnings": ["stale_market_data"] if is_stale else [],
    }


def test_refresh_falls_back_to_existing_universe(monkeypatch):
    monkeypatch.setattr(refresh, "build_market_data_freshness_status", lambda *_args, **_kwargs: _freshness())
    monkeypatch.setattr(refresh, "_latest_candle_dates_by_ticker", lambda *_args, **_kwargs: {"SBER": "2026-05-21"})
    monkeypatch.setattr(refresh, "_eligible_instrument_count", lambda *_args, **_kwargs: 10)
    monkeypatch.setattr(
        refresh,
        "bootstrap_moex_universe",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("MOEX request failed after 1 attempts")),
    )
    monkeypatch.setattr(
        refresh,
        "bootstrap_moex_candles",
        lambda *_args, **_kwargs: {
            "ok": True,
            "loaded_tickers": 1,
            "failed_tickers": 0,
            "inserted_candles": 0,
            "updated_candles": 2,
            "loaded": [{"ticker": "SBER", "updated": 2, "inserted": 0}],
            "failed": [],
            "skipped": [],
            "warnings": [],
        },
    )
    monkeypatch.setattr(refresh, "build_ticker_freshness_report", lambda *_args, **_kwargs: {"stale_tickers": []})

    result = refresh.refresh_market_data_daily(object(), max_tickers=1, request_timeout=3)

    assert result["ok"] is True
    assert result["universe_refresh_status"] == "fallback_existing"
    assert result["used_existing_universe"] is True
    assert "universe_refresh_failed" in result["warnings"]


def test_skip_universe_requires_existing_universe(monkeypatch):
    monkeypatch.setattr(refresh, "build_market_data_freshness_status", lambda *_args, **_kwargs: _freshness())
    monkeypatch.setattr(refresh, "_latest_candle_dates_by_ticker", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(refresh, "_eligible_instrument_count", lambda *_args, **_kwargs: 0)

    result = refresh.refresh_market_data_daily(object(), refresh_universe=False)

    assert result["ok"] is False
    assert result["universe_refresh_status"] == "missing"
    assert result["recommendation"] == "bootstrap_required"
