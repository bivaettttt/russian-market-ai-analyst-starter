import math

from app.services.ml_v2_dataset import FEATURE_NAMES, build_ml_v2_feature_row, build_ml_v2_trade_dataset


def test_build_ml_v2_trade_dataset_importable_and_callable():
    assert callable(build_ml_v2_trade_dataset)


def test_ml_v2_feature_row_numeric_and_no_nan():
    history = []
    for index in range(90):
        close = 100 + index * 0.2
        history.append(
            {
                "close": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "volume": 1_000_000 + index,
                "value": 100_000_000 + index * 1000,
            }
        )
    sample = {
        "history": history,
        "volatility_bucket": "medium",
        "liquidity_bucket": "high",
        "market_regime_name": "risk_on",
        "market_regime_score": 12.5,
        "market_regime": {"components": {"downside_pressure": 1, "breadth_score": 2, "trend_score": 3}},
        "target_return_pct": 3.0,
        "stop_return_pct": -2.0,
        "risk_reward_ratio": 1.5,
        "sector": "metals",
        "asset_type": "stock",
    }
    row = build_ml_v2_feature_row(sample)
    assert len(row) == len(FEATURE_NAMES)
    assert all(isinstance(value, float) for value in row)
    assert not any(math.isnan(value) or math.isinf(value) for value in row)
