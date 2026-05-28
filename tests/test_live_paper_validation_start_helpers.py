from app.services.live_paper_validation_start import should_block_live_validation_start


def test_live_validation_blocks_stale_when_required():
    blocked, reason = should_block_live_validation_start(
        require_fresh_market_data=True,
        market_freshness={
            "summary": {
                "tickers_with_candles": 10,
                "is_stale": True,
            }
        },
    )

    assert blocked is True
    assert reason == "market_data_stale"


def test_live_validation_allows_stale_when_not_required():
    blocked, reason = should_block_live_validation_start(
        require_fresh_market_data=False,
        market_freshness={
            "summary": {
                "tickers_with_candles": 10,
                "is_stale": True,
            }
        },
    )

    assert blocked is False
    assert reason is None


def test_live_validation_blocks_no_market_data():
    blocked, reason = should_block_live_validation_start(
        require_fresh_market_data=True,
        market_freshness={
            "summary": {
                "tickers_with_candles": 0,
                "is_stale": True,
            }
        },
    )

    assert blocked is True
    assert reason == "no_market_data"
