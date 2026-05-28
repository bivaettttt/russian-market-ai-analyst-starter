from app.services import event_overlay_paper_tracking as tracking


def test_csv_text_outputs_header_for_empty_rows():
    csv_text = tracking._csv_text(["metric", "value"], [])
    assert csv_text.startswith("metric,value")


def test_snapshot_csv_contract_uses_expected_headers(monkeypatch):
    monkeypatch.setattr(
        tracking,
        "list_event_overlay_paper_snapshots",
        lambda *_args, **_kwargs: {"rows": []},
    )

    csv_text = tracking.build_event_overlay_paper_snapshots_csv(object(), limit=5)

    assert "snapshot_id" in csv_text.splitlines()[0]
    assert "overlay_delta_pnl_pct" in csv_text.splitlines()[0]
