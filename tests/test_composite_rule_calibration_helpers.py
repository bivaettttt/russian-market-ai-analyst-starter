from app.services.composite_rule_calibration import (
    generate_composite_rules,
    sample_matches_rule,
    score_composite_rule_result,
)


def test_sample_matches_numeric_thresholds():
    sample = {"features": {"target_probability_pct": 58}}
    assert sample_matches_rule(sample, {"conditions": [{"field": "target_probability_pct", "op": ">=", "value": 55}]})
    assert not sample_matches_rule(sample, {"conditions": [{"field": "target_probability_pct", "op": ">=", "value": 60}]})


def test_sample_matches_regime_not_equal():
    sample = {"features": {"market_regime": "neutral"}}
    assert sample_matches_rule(sample, {"conditions": [{"field": "market_regime", "op": "!=", "value": "risk_off"}]})
    assert not sample_matches_rule({"features": {"market_regime": "risk_off"}}, {"conditions": [{"field": "market_regime", "op": "!=", "value": "risk_off"}]})


def test_sample_matches_in_and_not_in():
    sample = {"features": {"volatility_bucket": "medium", "audit_confidence": "high"}}
    assert sample_matches_rule(sample, {"conditions": [{"field": "audit_confidence", "op": "in", "value": ["medium", "high"]}]})
    assert sample_matches_rule(sample, {"conditions": [{"field": "volatility_bucket", "op": "not_in", "value": ["high", "extreme"]}]})


def test_missing_field_false_except_exists_ops():
    sample = {"features": {}}
    assert not sample_matches_rule(sample, {"conditions": [{"field": "target_probability_pct", "op": ">=", "value": 55}]})
    assert not sample_matches_rule(sample, {"conditions": [{"field": "market_regime", "op": "!=", "value": "risk_off"}]})
    assert not sample_matches_rule(sample, {"conditions": [{"field": "market_regime", "op": "exists"}]})
    assert sample_matches_rule(sample, {"conditions": [{"field": "market_regime", "op": "not_exists"}]})


def test_generate_composite_rules_respects_limit():
    rules = generate_composite_rules(max_rules=7)
    assert len(rules) == 7
    assert rules[0]["rule_id"].startswith("prob")
    assert all("conditions" in rule for rule in rules)


def test_score_rewards_better_rule_result():
    weak = {
        "selected_samples": 120,
        "coverage_pct": 50,
        "selected_avg_trade_return_pct": -0.1,
        "selected_profit_factor": 0.95,
        "selected_win_rate_pct": 50,
        "baseline_win_rate_pct": 50,
        "selected_stop_hit_rate_pct": 47,
        "baseline_stop_hit_rate_pct": 47,
        "avg_trade_return_delta_pct": 0,
        "profit_factor_delta": 0,
    }
    strong = {
        **weak,
        "selected_avg_trade_return_pct": 0.25,
        "selected_profit_factor": 1.18,
        "selected_win_rate_pct": 56,
        "selected_stop_hit_rate_pct": 40,
        "avg_trade_return_delta_pct": 0.35,
        "profit_factor_delta": 0.23,
    }
    assert score_composite_rule_result(strong, min_trades=50) > score_composite_rule_result(weak, min_trades=50)
