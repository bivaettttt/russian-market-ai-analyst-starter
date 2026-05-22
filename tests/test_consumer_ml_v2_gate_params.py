from app.services.consumer_signals import compare_consumer_ml_v2_gate_snapshot, normalize_ml_v2_gate_mode


def test_ml_v2_gate_mode_normalization():
    assert normalize_ml_v2_gate_mode(None) == "diagnostic_only"
    assert normalize_ml_v2_gate_mode("soft_downgrade") == "soft_downgrade"
    assert normalize_ml_v2_gate_mode("hard_gate") == "hard_gate"
    assert normalize_ml_v2_gate_mode("bad") == "diagnostic_only"


def test_consumer_ml_v2_gate_compare_export_is_callable():
    assert callable(compare_consumer_ml_v2_gate_snapshot)

