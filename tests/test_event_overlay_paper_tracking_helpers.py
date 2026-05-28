from app.services.event_overlay_paper_tracking import (
    calculate_overlay_delta_pnl_pct,
    calculate_position_pnl_pct,
    classify_realized_outcome,
)


def test_position_pnl_uses_position_size_pct_units():
    assert calculate_position_pnl_pct(10.0, 5.0) == 0.5
    assert calculate_position_pnl_pct(-4.0, 2.5) == -0.1


def test_overlay_delta_is_overlay_minus_baseline():
    assert calculate_overlay_delta_pnl_pct(0.5, 0.3) == -0.2
    assert calculate_overlay_delta_pnl_pct(-0.5, -0.2) == 0.3


def test_insufficient_data_outcome():
    assert classify_realized_outcome(None) == "insufficient_data"
    assert classify_realized_outcome(1.0) == "positive"
    assert classify_realized_outcome(-1.0) == "negative"
    assert classify_realized_outcome(0.0) == "timeout"
