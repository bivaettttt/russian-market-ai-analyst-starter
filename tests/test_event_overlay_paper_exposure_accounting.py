from app.services import event_overlay_paper_snapshot as snapshot
from app.services.event_overlay_paper_tracking import (
    calculate_overlay_delta_pnl_pct,
    calculate_position_pnl_pct,
    paper_position_size_or_fallback,
)


def test_row_without_position_size_uses_paper_fallback():
    size, source = snapshot.resolve_paper_position_size({})

    assert size == snapshot.DEFAULT_PAPER_POSITION_SIZE_PCT
    assert source == "fallback_default"


def test_signal_position_size_wins_over_fallback():
    size, source = snapshot.resolve_paper_position_size({"position_sizing": {"max_position_pct": 2.5}})

    assert size == 2.5
    assert source == "signal"


def test_snapshot_exposure_uses_fallback_default(monkeypatch):
    rows = [
        {
            "ticker": f"T{i}",
            "action": "watch",
            "price": 100,
            "event_risk_position_multiplier": 0.8,
            "event_risk_level": "elevated",
            "event_risk_score": 40,
            "event_risk_reasons": [],
            "event_risk_matched_rule_ids": [],
        }
        for i in range(10)
    ]

    calls = {"count": 0}

    def _list_consumer_signals(**_kwargs):
        calls["count"] += 1
        return {"rows": rows}

    monkeypatch.setattr(snapshot, "list_consumer_signals", _list_consumer_signals)

    result = snapshot.build_event_overlay_paper_snapshot(object(), limit=10)
    summary = result["summary"]

    assert calls["count"] == 2
    assert summary["baseline_total_exposure"] == 10.0
    assert summary["overlay_total_exposure"] == 8.0
    assert summary["exposure_reduction_pct"] == 20.0
    assert summary["position_size_source"] == "fallback_default"
    assert result["rows"][0]["base_position_size_pct"] == 1.0
    assert result["rows"][0]["event_adjusted_position_size_pct"] == 0.8


def test_evaluation_pnl_uses_position_exposure_units():
    baseline_pnl = calculate_position_pnl_pct(5.0, 1.0)
    overlay_pnl = calculate_position_pnl_pct(5.0, 0.8)

    assert baseline_pnl == 0.05
    assert overlay_pnl == 0.04
    assert calculate_overlay_delta_pnl_pct(baseline_pnl, overlay_pnl) == -0.010000000000000002


def test_legacy_zero_position_size_gets_fallback_for_evaluation():
    size, used_fallback = paper_position_size_or_fallback(0.0)

    assert size == 1.0
    assert used_fallback is True
