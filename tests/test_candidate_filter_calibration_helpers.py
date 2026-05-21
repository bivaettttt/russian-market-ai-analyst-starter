from app.services.candidate_filter_calibration import apply_candidate_filter, score_filter_result


def test_apply_exclude_ticker_filter():
    config = {
        "filter_type": "exclude",
        "rules": [{"dimension": "ticker", "op": "!=", "value": "GLRX"}],
    }
    assert apply_candidate_filter({"ticker": "SBER"}, config) is True
    assert apply_candidate_filter({"ticker": "GLRX"}, config) is False


def test_apply_include_only_market_regime_filter():
    config = {
        "filter_type": "include_only",
        "rules": [{"dimension": "market_regime", "op": "==", "value": "risk_on"}],
    }
    assert apply_candidate_filter({"market_regime_name": "risk_on"}, config) is True
    assert apply_candidate_filter({"market_regime_name": "risk_off"}, config) is False


def test_apply_combo_exclude_high_vol_low_liquidity():
    config = {
        "filter_type": "combo_exclude",
        "rules": [
            {"dimension": "volatility_bucket", "op": "in", "value": ["high", "extreme"]},
            {"dimension": "liquidity_bucket", "op": "==", "value": "low"},
        ],
    }
    assert apply_candidate_filter({"segments": {"volatility_bucket": "high", "liquidity_bucket": "low"}}, config) is False
    assert apply_candidate_filter({"segments": {"volatility_bucket": "medium", "liquidity_bucket": "low"}}, config) is True


def test_unknown_fields_do_not_crash():
    config = {
        "filter_type": "exclude",
        "rules": [{"dimension": "unknown_dimension", "op": "!=", "value": "bad"}],
    }
    assert apply_candidate_filter({}, config) is True


def test_score_rewards_improvement():
    good = {
        "avg_trade_return_delta_pct": 0.2,
        "profit_factor_delta": 0.3,
        "win_rate_delta_pct": 4,
        "stop_hit_delta_pct": -5,
        "avoided_losses": 30,
        "missed_wins": 5,
        "kept_samples": 100,
        "coverage_after_filter_pct": 80,
    }
    weak = {
        "avg_trade_return_delta_pct": 0,
        "profit_factor_delta": 0,
        "win_rate_delta_pct": 0,
        "stop_hit_delta_pct": 0,
        "avoided_losses": 0,
        "missed_wins": 0,
        "kept_samples": 100,
        "coverage_after_filter_pct": 80,
    }
    assert score_filter_result(good, min_bucket_samples=20) > score_filter_result(weak, min_bucket_samples=20)
