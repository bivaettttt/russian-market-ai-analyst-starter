from app.services.event_overlay_paper_tracking_page_html import build_event_overlay_paper_tracking_page_html
from app.services.event_overlay_quality_report_page_html import build_event_overlay_quality_report_page_html
from app.services.live_paper_validation_page_html import build_live_paper_validation_page_html
from app.services.market_daily_ops_page_html import build_market_daily_ops_page_html
from app.services.market_refresh_report_page_html import build_market_refresh_report_page_html
from app.services.signals_page_html import build_signals_page_html
from app.services.ticker_page_html import build_ticker_page_html


def test_product_pages_use_product_shell_and_clean_nav():
    pages = [
        build_signals_page_html(),
        build_ticker_page_html("SBER"),
        build_live_paper_validation_page_html(),
        build_event_overlay_quality_report_page_html(),
        build_event_overlay_paper_tracking_page_html(),
        build_market_daily_ops_page_html(),
        build_market_refresh_report_page_html(),
    ]

    for html in pages:
        assert "product-shell" in html
        assert "app-topbar" in html
        assert "Research Hub" not in html or "/signals/research-hub-page" in html


def test_user_pages_hide_raw_payloads_by_default():
    for html in [
        build_signals_page_html(),
        build_ticker_page_html("SBER"),
        build_event_overlay_quality_report_page_html(),
    ]:
        assert "<details" in html or "Advanced" in html
        assert "JSON.stringify" in html
        assert "Raw" not in html.split("<main", 1)[0]
