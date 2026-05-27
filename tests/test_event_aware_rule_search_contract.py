from app.services.event_aware_rule_search import build_event_aware_rule_search


def test_event_aware_rule_search_contract_importable():
    assert callable(build_event_aware_rule_search)
