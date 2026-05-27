from app.services.event_aware_dual_side_research import (
    build_event_aware_dual_side_research,
    build_event_aware_dual_side_walk_forward,
)


def test_event_aware_dual_side_contract_importable():
    assert callable(build_event_aware_dual_side_research)
    assert callable(build_event_aware_dual_side_walk_forward)
