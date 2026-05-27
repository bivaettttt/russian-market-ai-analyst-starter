from app.services.setup_candidate_generator import classify_setup_families, pick_primary_setup_family


def _candles(closes: list[float], volume: float = 1000, value: float = 100_000_000):
    return [
        {"open": close, "high": close * 1.01, "low": close * 0.99, "close": close, "volume": volume, "value": value}
        for close in closes
    ]


def test_breakout_mock_triggers_breakout():
    closes = [100 + i * 0.1 for i in range(55)] + [106, 107, 108, 109, 112]
    candles = _candles(closes)
    candles[-1]["volume"] = 1500
    result = classify_setup_families(candles)
    assert result["ok"] is True
    assert result["setups"]["breakout"]["active"] is True


def test_mean_reversion_mock_triggers_mean_reversion():
    closes = [120 - i * 0.1 for i in range(55)] + [112, 110, 108, 106, 105]
    result = classify_setup_families(_candles(closes), config={"mean_reversion_dist_low_pct": 3})
    assert result["ok"] is True
    assert result["setups"]["mean_reversion"]["active"] is True


def test_short_candles_no_crash():
    result = classify_setup_families(_candles([100, 101, 102]))
    assert result["ok"] is False
    assert result["warnings"]


def test_primary_picks_highest_active_score():
    primary = pick_primary_setup_family(
        {
            "breakout": {"active": True, "score": 55},
            "pullback": {"active": True, "score": 75},
            "mean_reversion": {"active": False, "score": 90},
        }
    )
    assert primary == "pullback"
