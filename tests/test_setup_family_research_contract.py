from app.services.setup_family_research import build_setup_family_parameter_sweep, build_setup_family_research


def test_setup_family_research_contract_importable():
    assert callable(build_setup_family_research)
    assert callable(build_setup_family_parameter_sweep)
