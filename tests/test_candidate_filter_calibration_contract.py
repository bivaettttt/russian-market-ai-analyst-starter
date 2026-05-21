from app.services.candidate_filter_calibration import build_candidate_filter_calibration


def test_candidate_filter_calibration_builder_is_callable():
    assert callable(build_candidate_filter_calibration)
