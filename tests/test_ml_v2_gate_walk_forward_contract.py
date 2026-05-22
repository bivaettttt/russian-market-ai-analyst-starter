from app.services.ml_v2_gate_walk_forward import build_ml_v2_gate_walk_forward


def test_ml_v2_gate_walk_forward_builder_is_callable():
    assert callable(build_ml_v2_gate_walk_forward)
