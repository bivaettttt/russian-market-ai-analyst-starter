from app.services.event_aware_setup_research import (
    build_event_aware_setup_research,
    build_event_aware_setup_sweep,
    build_event_coverage_diagnostics,
)


def test_event_aware_research_contract_importable():
    assert callable(build_event_aware_setup_research)
    assert callable(build_event_aware_setup_sweep)
    assert callable(build_event_coverage_diagnostics)
