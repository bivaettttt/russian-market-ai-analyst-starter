from app.services.adaptive_trade_calibration import compute_trade_setup, normalize_trade_policy


def _candles(count: int = 40, start: float = 100.0, step: float = 0.2):
    rows = []
    for idx in range(count):
        close = start + step * idx
        rows.append(
            {
                "trade_date": f"2024-02-{(idx % 28) + 1:02d}",
                "open": close - 0.2,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": 100_000,
                "value": 100_000_000,
            }
        )
    return rows


def test_fixed_pct_policy_matches_baseline_shape():
    candles = _candles()
    close = candles[-1]["close"]
    setup = compute_trade_setup(
        close=close,
        candles=candles,
        policy={"policy_type": "fixed_pct", "target_pct": 0.05, "stop_pct": 0.03, "horizon": 20, "min_rr": 1.0},
    )

    assert setup["ok"] is True
    assert setup["target_pct"] == 5.0
    assert setup["stop_pct"] == 3.0
    assert setup["risk_reward_ratio"] == 1.67
    assert setup["target_price"] > close
    assert setup["stop_price"] < close


def test_atr_policy_builds_positive_rr_setup():
    candles = _candles()
    close = candles[-1]["close"]
    setup = compute_trade_setup(
        close=close,
        candles=candles,
        policy={"policy_type": "atr_multiple", "target_atr_mult": 2.0, "stop_atr_mult": 1.1, "horizon": 20},
    )

    assert setup["target_price"] > close
    assert setup["stop_price"] < close
    assert setup["risk_reward_ratio"] > 0
    assert setup["atr_pct"] is not None


def test_low_data_policy_does_not_crash_and_warns():
    candles = _candles(count=5)
    setup = compute_trade_setup(
        close=candles[-1]["close"],
        candles=candles,
        policy={"policy_type": "atr_multiple"},
    )

    assert setup["ok"] is True
    assert setup["warnings"]


def test_normalize_trade_policy_is_stable():
    policy = normalize_trade_policy({"policy_type": "unknown", "target_pct": 9, "stop_pct": -1, "horizon": 999})

    assert policy["policy_type"] == "fixed_pct"
    assert policy["target_pct"] == 0.25
    assert policy["stop_pct"] == 0.005
    assert policy["horizon"] == 90
