from app.services.ml_v2_gate_impact_evaluation import build_ml_v2_gate_impact_evaluation


def test_ml_v2_gate_impact_builder_is_callable():
    assert callable(build_ml_v2_gate_impact_evaluation)
