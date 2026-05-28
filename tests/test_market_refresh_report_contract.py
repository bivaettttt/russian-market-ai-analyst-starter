from app.services import market_refresh_report as report


def test_market_refresh_report_contract_imports():
    assert callable(report.build_market_refresh_report)
    assert callable(report.build_market_refresh_notification)
    assert callable(report.build_market_refresh_report_csv)


def test_market_refresh_report_csv_header(monkeypatch):
    monkeypatch.setattr(
        report,
        "build_market_refresh_report",
        lambda *_args, **_kwargs: {
            "ticker_freshness": {
                "fresh_tickers": [],
                "stale_tickers": [],
                "missing_candles_tickers": [],
            }
        },
    )

    csv_text = report.build_market_refresh_report_csv(object())

    assert csv_text.startswith("ticker,latest_candle_date,days_stale,status")
