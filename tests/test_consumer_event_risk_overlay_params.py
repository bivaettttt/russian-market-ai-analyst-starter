from app.services.consumer_signals import normalize_event_risk_overlay_mode


def test_event_risk_overlay_mode_normalization():
    assert normalize_event_risk_overlay_mode("diagnostic_only") == "diagnostic_only"
    assert normalize_event_risk_overlay_mode("soft_adjust") == "soft_adjust"
    assert normalize_event_risk_overlay_mode("experimental_downgrade") == "experimental_downgrade"
    assert normalize_event_risk_overlay_mode("bad") == "diagnostic_only"
    assert normalize_event_risk_overlay_mode(None) == "diagnostic_only"
