from app.services.event_aware_walk_forward import (
    concentration_risk,
    create_walk_forward_folds,
    event_aware_combo_key,
    recommendation_from_summary,
    select_top_train_combos,
)


def _row(date: str, ticker: str = "SBER", ret: float = 1.0, combo: str = "rates"):
    return {
        "date": date,
        "ticker": ticker,
        "setup_family": "pullback",
        "event_family": combo,
        "event_direction": "positive",
        "event_confirmation": "confirmed",
        "event_id": f"{combo}_{date}",
        "outcome": "target_hit" if ret > 0 else "stop_hit",
        "trade_return_pct": ret,
    }


def test_combo_key_detailed_and_simple():
    row = _row("2024-01-01")
    assert event_aware_combo_key(row) == "pullback+rates+positive+confirmed"
    assert event_aware_combo_key(row, detailed=False) == "pullback+rates"


def test_fold_split_no_overlap_train_before_test():
    rows = [_row(f"2024-01-{day:02d}", ticker=f"T{day}") for day in range(1, 31)]
    folds = create_walk_forward_folds(rows, folds=3, train_ratio=0.6, min_train_samples=10, min_test_samples=3)
    assert folds
    for fold in folds:
        train_dates = [row["date"] for row in fold["train_rows"]]
        test_dates = [row["date"] for row in fold["test_rows"]]
        assert max(train_dates) < min(test_dates)
        assert not set(train_dates) & set(test_dates)


def test_select_top_train_combos_respects_min_signals_and_score():
    rows = [_row(f"2024-01-{day:02d}", ret=1.0, combo="rates") for day in range(1, 8)]
    rows += [_row(f"2024-02-{day:02d}", ret=-1.0, combo="fx") for day in range(1, 8)]
    rows += [_row("2024-03-01", ret=5.0, combo="oil_gas")]
    selected = select_top_train_combos(rows, min_signals=3, top_k=2)
    keys = [row["combo_key"] for row in selected]
    assert "pullback+oil_gas+positive+confirmed" not in keys
    assert keys[0] == "pullback+rates+positive+confirmed"


def test_concentration_risk_detects_top_ticker_share():
    rows = [_row(f"2024-01-{day:02d}", ticker="SBER") for day in range(1, 8)]
    rows += [_row("2024-01-08", ticker="LKOH")]
    result = concentration_risk(rows)
    assert result["top_ticker_share_pct"] > 50
    assert result["warnings"]


def test_recommendation_promising_and_research_only_on_concentration():
    summary = {
        "event_samples": 200,
        "folds_completed": 4,
        "positive_folds": 3,
        "avg_test_selected_profit_factor": 1.2,
        "avg_test_selected_return_pct": 0.4,
    }
    assert recommendation_from_summary(summary, concentration_warning=False) == "promising_event_edge"
    assert recommendation_from_summary(summary, concentration_warning=True) == "research_only"
    summary["event_samples"] = 10
    assert recommendation_from_summary(summary, concentration_warning=False) == "needs_more_event_data"
