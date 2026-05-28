from app.services.event_aware_risk_overlay_walk_forward import (
    apply_overlay_config_to_sample,
    build_event_risk_overlay_walk_forward,
    calculate_overlay_weighted_metrics,
    generate_event_risk_overlay_configs,
)


def test_event_risk_overlay_walk_forward_contract_imports():
    assert callable(build_event_risk_overlay_walk_forward)
    assert callable(generate_event_risk_overlay_configs)
    assert callable(apply_overlay_config_to_sample)
    assert callable(calculate_overlay_weighted_metrics)
