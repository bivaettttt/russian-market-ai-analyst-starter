from app.services.event_overlay_paper_tracking import classify_paper_snapshot


def _snapshot(**overrides):
    data = {
        "name": "manual",
        "source": "conservative_event_overlay",
        "snapshot_date": "2026-05-29",
        "horizon_days": 20,
        "baseline_total_exposure": 10.0,
        "overlay_total_exposure": 9.0,
        "exposure_reduction_pct": 10.0,
        "summary": {"position_size_source": "fallback_default"},
    }
    data.update(overrides)
    return data


def test_official_daily_with_positive_exposure_is_official():
    info = classify_paper_snapshot(_snapshot(name="official-daily-2026-05-29"))

    assert info["snapshot_type"] == "official"
    assert info["is_official"] is True
    assert info["is_legacy"] is False
    assert info["next_evaluation_date"] == "2026-06-18"


def test_zero_exposure_is_legacy_even_with_manual_name():
    info = classify_paper_snapshot(
        _snapshot(
            name="manual",
            baseline_total_exposure=0.0,
            overlay_total_exposure=0.0,
        )
    )

    assert info["snapshot_type"] == "legacy"
    assert info["has_zero_exposure"] is True


def test_test_name_is_test_when_exposure_is_valid():
    info = classify_paper_snapshot(_snapshot(name="exposure-fix-test"))

    assert info["snapshot_type"] == "test"
    assert info["is_test"] is True


def test_manual_name_with_exposure_is_manual():
    info = classify_paper_snapshot(_snapshot(name="manual-daily"))

    assert info["snapshot_type"] == "manual"
    assert info["is_official"] is False
