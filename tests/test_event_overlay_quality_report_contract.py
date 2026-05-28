from app.services import event_overlay_quality_report as report


def test_quality_report_contract_imports():
    assert callable(report.build_conservative_overlay_quality_report)
    assert callable(report.build_conservative_overlay_notification_summary)
    assert callable(report.build_conservative_overlay_data_health)
    assert callable(report.build_conservative_overlay_quality_report_csv)


def test_quality_report_csv_has_header(monkeypatch):
    monkeypatch.setattr(
        report,
        "build_conservative_overlay_quality_report",
        lambda *_args, **_kwargs: {
            "summary": {},
            "by_risk_level": [],
            "recent_snapshots": [],
            "top_positive_contributors": [],
            "top_negative_contributors": [],
        },
    )

    csv_text = report.build_conservative_overlay_quality_report_csv(object(), limit=5)

    assert csv_text.startswith("section,metric,value")
