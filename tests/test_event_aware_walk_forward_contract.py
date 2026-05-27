from app.services.event_aware_walk_forward import build_event_aware_walk_forward


def test_event_aware_walk_forward_contract_importable():
    assert callable(build_event_aware_walk_forward)
