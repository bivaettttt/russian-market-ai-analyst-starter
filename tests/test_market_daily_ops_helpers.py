from app.services.market_daily_ops import merge_daily_ops_warnings, select_daily_ops_recommended_action


def test_daily_ops_recommended_action_prefers_stale_data():
    assert (
        select_daily_ops_recommended_action(
            market_data_stale=True,
            ready_snapshots=0,
            created_snapshot=False,
            duplicate_snapshot=True,
            quality_label="improving",
        )
        == "refresh_market_data"
    )


def test_daily_ops_recommended_action_ready_snapshots():
    assert (
        select_daily_ops_recommended_action(
            market_data_stale=False,
            ready_snapshots=2,
            created_snapshot=False,
            duplicate_snapshot=True,
            quality_label="mixed",
        )
        == "evaluate_ready"
    )


def test_daily_ops_recommended_action_snapshot_created():
    assert (
        select_daily_ops_recommended_action(
            market_data_stale=False,
            ready_snapshots=0,
            created_snapshot=True,
            duplicate_snapshot=False,
            quality_label="insufficient_data",
        )
        == "review_dashboard"
    )


def test_daily_ops_warning_merge_deduplicates():
    warnings = merge_daily_ops_warnings(
        {"warnings": ["stale_market_data"], "summary": {"is_stale": True}},
        {"warnings": ["no_evaluated_items"]},
    )

    assert warnings == ["no_evaluated_items", "stale_market_data"]
