from app.services.expectancy_breakdown import (
    bucket_liquidity,
    bucket_ml_probability,
    bucket_probability,
    bucket_rr,
    bucket_volatility,
    quality_label_for_bucket,
)


def test_bucket_probability():
    assert bucket_probability(None) == "unknown"
    assert bucket_probability(39.9) == "<40"
    assert bucket_probability(40) == "40-50"
    assert bucket_probability(50) == "50-60"
    assert bucket_probability(60) == "60-70"
    assert bucket_probability(70) == ">=70"


def test_bucket_ml_probability():
    assert bucket_ml_probability(None) == "unknown"
    assert bucket_ml_probability(14.9) == "<15"
    assert bucket_ml_probability(15) == "15-25"
    assert bucket_ml_probability(25) == "25-35"
    assert bucket_ml_probability(35) == ">=35"


def test_bucket_rr():
    assert bucket_rr(None) == "unknown"
    assert bucket_rr(0.79) == "<0.8"
    assert bucket_rr(0.8) == "0.8-1.0"
    assert bucket_rr(1.0) == "1.0-1.2"
    assert bucket_rr(1.2) == "1.2-1.5"
    assert bucket_rr(1.5) == ">=1.5"


def test_bucket_volatility_and_liquidity():
    assert bucket_volatility(None) == "unknown"
    assert bucket_volatility(1.0) == "low"
    assert bucket_volatility(2.0) == "medium"
    assert bucket_volatility(3.0) == "high"
    assert bucket_volatility(4.0) == "extreme"
    assert bucket_liquidity(None) == "unknown"
    assert bucket_liquidity(0.5) == "low"
    assert bucket_liquidity(1.0) == "medium"
    assert bucket_liquidity(1.5) == "high"


def test_quality_label_for_bucket():
    assert quality_label_for_bucket({"samples": 5}, min_bucket_samples=20) == "unstable"
    assert quality_label_for_bucket(
        {"samples": 20, "avg_trade_return_pct": 0.2, "profit_factor": 1.1},
        min_bucket_samples=20,
    ) == "positive"
    assert quality_label_for_bucket(
        {"samples": 20, "avg_trade_return_pct": -0.2, "profit_factor": 0.9},
        min_bucket_samples=20,
    ) == "negative"
    assert quality_label_for_bucket(
        {"samples": 20, "avg_trade_return_pct": 0.0, "profit_factor": 1.0},
        min_bucket_samples=20,
    ) == "neutral"
