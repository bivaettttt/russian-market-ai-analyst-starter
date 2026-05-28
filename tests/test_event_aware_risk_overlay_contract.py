from app.services.event_aware_risk_overlay import (
    apply_event_risk_overlay_to_signal,
    build_event_aware_risk_overlay,
    match_event_risk_rules_for_signal,
    score_event_risk_overlay,
)
from app.services.event_aware_risk_overlay_backtest import build_event_risk_overlay_backtest


def test_event_aware_risk_overlay_contract_imports():
    assert callable(build_event_aware_risk_overlay)
    assert callable(score_event_risk_overlay)
    assert callable(apply_event_risk_overlay_to_signal)
    assert callable(match_event_risk_rules_for_signal)
    assert callable(build_event_risk_overlay_backtest)
