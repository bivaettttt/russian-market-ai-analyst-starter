import math

from app.services.ml_v3_consumer_candidate_dataset import (
    FEATURE_NAMES,
    build_ml_v3_consumer_candidate_feature_row,
    is_consumer_long_candidate_action,
)


def test_consumer_long_candidate_mapping():
    assert is_consumer_long_candidate_action("buy") is True
    assert is_consumer_long_candidate_action("consider_buy") is True
    assert is_consumer_long_candidate_action("watch_ml_confirmed") is True
    assert is_consumer_long_candidate_action("watch") is False
    assert is_consumer_long_candidate_action("avoid") is False
    assert is_consumer_long_candidate_action("watch", include_watch_candidates=True) is True


def test_feature_row_numeric_stable_no_nan():
    sample = {
        "baseline_action": "buy",
        "probability_pct": 62,
        "risk_reward_ratio": 1.4,
        "audit_score": 70,
        "audit_confidence_level": "high",
        "history": [
            {"close": 100 + i, "high": 101 + i, "low": 99 + i, "volume": 1000 + i, "value": 100000 + i}
            for i in range(70)
        ],
        "market_regime_name": "risk_on",
        "market_regime_score": 20,
        "target_return_pct": 5.0,
        "stop_return_pct": -3.0,
    }
    row = build_ml_v3_consumer_candidate_feature_row(sample)
    assert len(row) == len(FEATURE_NAMES)
    assert all(isinstance(value, float) for value in row)
    assert not any(math.isnan(value) for value in row)
    assert FEATURE_NAMES == list(FEATURE_NAMES)
