from app.services.market_refresh_report import build_market_refresh_notification


class _DB:
    pass


def test_market_refresh_notification_for_stale(monkeypatch):
    from app.services import market_refresh_report as report

    monkeypatch.setattr(
        report,
        "build_market_refresh_report",
        lambda *_args, **_kwargs: {
            "summary": {
                "latest_candle_date": "2026-05-21",
                "market_data_stale": True,
                "recommended_action": "refresh_market_data",
            },
            "ticker_freshness": {"stale_tickers": [{"ticker": "SBER", "days_stale": 7}]},
            "warnings": ["stale_market_data"],
        },
    )

    result = build_market_refresh_notification(_DB())

    assert result["status"] == "warning"
    assert result["recommended_action"] == "refresh_market_data"
    assert "stale" in result["message"]


def test_market_refresh_notification_for_no_data(monkeypatch):
    from app.services import market_refresh_report as report

    monkeypatch.setattr(
        report,
        "build_market_refresh_report",
        lambda *_args, **_kwargs: {
            "summary": {
                "latest_candle_date": None,
                "market_data_stale": True,
                "recommended_action": "bootstrap_required",
            },
            "ticker_freshness": {},
            "warnings": ["no_market_candles"],
        },
    )

    result = build_market_refresh_notification(_DB())

    assert result["status"] == "critical"
    assert result["recommended_action"] == "bootstrap_required"
