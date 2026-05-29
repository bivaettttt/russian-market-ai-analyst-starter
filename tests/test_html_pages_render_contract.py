from app.services.data_coverage_page_html import build_data_coverage_page_html
from app.services.event_overlay_paper_tracking_page_html import build_event_overlay_paper_tracking_page_html
from app.services.event_overlay_quality_report_page_html import build_event_overlay_quality_report_page_html
from app.services.live_paper_validation_page_html import build_live_paper_validation_page_html
from app.services.market_daily_ops_page_html import build_market_daily_ops_page_html
from app.services.market_refresh_report_page_html import build_market_refresh_report_page_html
from app.services.research_hub_page_html import build_research_hub_page_html
from app.services.signals_page_html import build_signals_page_html
from app.services.ticker_page_html import build_ticker_page_html
from app.services.ui_theme import THEME_MARKER, enhance_html_document


def test_key_html_pages_render_and_can_be_themed():
    pages = [
        build_signals_page_html(),
        build_ticker_page_html("SBER"),
        build_market_daily_ops_page_html(),
        build_live_paper_validation_page_html(),
        build_market_refresh_report_page_html(),
        build_event_overlay_quality_report_page_html(),
        build_event_overlay_paper_tracking_page_html(),
        build_data_coverage_page_html(),
    ]

    for page in pages:
        assert "<html" in page.lower()
        themed = enhance_html_document(page)
        assert THEME_MARKER in themed
        assert "app-topbar" in themed


def test_research_hub_links_major_sections():
    page = build_research_hub_page_html()

    assert THEME_MARKER in page
    assert "/signals/consumer/backtest-audit-page" in page
    assert "/signals/event-aware/rule-stability-page" in page
    assert "/signals/daily-ops/page" in page
    assert "Live Paper Validation Alpha" in page
