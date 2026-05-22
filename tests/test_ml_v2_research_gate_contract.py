from app.services.ml_v2_research_gate import (
    classify_ml_v2_gate_probability,
    load_ml_v2_research_model,
    score_ml_v2_research_gate,
)


def test_ml_v2_research_gate_exports_are_callable():
    assert callable(load_ml_v2_research_model)
    assert callable(score_ml_v2_research_gate)


def test_classify_ml_v2_gate_probability_threshold_logic():
    passed = classify_ml_v2_gate_probability(56.0, 55.0)
    rejected = classify_ml_v2_gate_probability(54.0, 55.0)

    assert passed["status"] == "passed"
    assert passed["gate_passed"] is True
    assert rejected["status"] == "rejected"
    assert rejected["gate_passed"] is False
