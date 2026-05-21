from app.services.market_regime import _build_regime_from_metrics, build_market_regime


def _metric(**overrides):
    base = {
        "above_sma20": True,
        "ret5_positive": True,
        "ret20_positive": True,
        "ret20_below_minus5": False,
        "near_20d_low": False,
        "negative_momentum": False,
        "volatility20_pct": 1.5,
    }
    base.update(overrides)
    return base


def test_market_regime_live_builder_is_callable():
    assert callable(build_market_regime)


def test_market_regime_fallback_contract_for_insufficient_data():
    result = _build_regime_from_metrics(
        metrics=[],
        mode="test_market_regime",
        lookback=60,
        warnings=[],
    )

    assert result["ok"] is True
    assert result["regime"] == "neutral"
    assert result["long_allowed"] is True
    assert "insufficient_market_regime_data" in result["warnings"]
    assert isinstance(result["reasons"], list)


def test_market_regime_risk_on_contract_from_breadth():
    result = _build_regime_from_metrics(
        metrics=[_metric() for _ in range(12)],
        mode="test_market_regime",
        lookback=60,
        warnings=[],
    )

    assert result["ok"] is True
    assert result["regime"] == "risk_on"
    assert result["regime_score"] > 0
    assert result["position_multiplier"] >= 1.0
