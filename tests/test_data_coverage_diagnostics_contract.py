from app.services.data_coverage_diagnostics import (
    build_data_coverage_diagnostics,
    classify_coverage_level,
    classify_ticker_data_status,
)


def test_data_coverage_builder_is_callable():
    assert callable(build_data_coverage_diagnostics)


def test_classify_ticker_data_status():
    assert (
        classify_ticker_data_status(
            is_signal_eligible=True,
            asset_type="stock",
            candle_count=0,
            valid_ohlc_count=0,
            min_history=80,
            horizon=20,
        )
        == "no_candles"
    )
    assert (
        classify_ticker_data_status(
            is_signal_eligible=True,
            asset_type="stock",
            candle_count=50,
            valid_ohlc_count=50,
            min_history=80,
            horizon=20,
        )
        == "too_few_candles"
    )
    assert (
        classify_ticker_data_status(
            is_signal_eligible=True,
            asset_type="stock",
            candle_count=90,
            valid_ohlc_count=90,
            min_history=80,
            horizon=20,
        )
        == "insufficient_horizon"
    )
    assert (
        classify_ticker_data_status(
            is_signal_eligible=True,
            asset_type="stock",
            candle_count=120,
            valid_ohlc_count=120,
            min_history=80,
            horizon=20,
        )
        == "ok"
    )


def test_classify_ticker_data_status_mapping_blockers():
    assert (
        classify_ticker_data_status(
            is_signal_eligible=False,
            asset_type="stock",
            candle_count=120,
            valid_ohlc_count=120,
            min_history=80,
            horizon=20,
        )
        == "not_signal_eligible"
    )
    assert (
        classify_ticker_data_status(
            is_signal_eligible=True,
            asset_type="bond",
            candle_count=120,
            valid_ohlc_count=120,
            min_history=80,
            horizon=20,
        )
        == "unsupported_asset_type"
    )
    assert (
        classify_ticker_data_status(
            is_signal_eligible=True,
            asset_type="stock",
            candle_count=120,
            valid_ohlc_count=0,
            min_history=80,
            horizon=20,
        )
        == "invalid_ohlc"
    )


def test_classify_coverage_level():
    assert classify_coverage_level(0, 0) == "empty"
    assert classify_coverage_level(100, 20) == "weak"
    assert classify_coverage_level(1000, 20) == "medium"
    assert classify_coverage_level(6000, 60) == "good"
