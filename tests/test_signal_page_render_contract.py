from app.services.signals_page_html import build_signals_page_html
from app.services.ticker_page_html import build_ticker_page_html


def test_signals_page_has_product_watchlist_structure():
    html = build_signals_page_html()

    assert "Signals" in html
    assert "signal-list" in html
    assert "signal-card" in html
    assert "Conservative overlay" in html
    assert "Advanced diagnostics" in html
    assert "/signals/consumer.json" in html


def test_ticker_page_has_user_facing_sections():
    html = build_ticker_page_html("SBER")

    assert "SBER Detail" in html
    assert "Why this signal?" in html
    assert "Conservative Event Overlay" in html
    assert "Advanced technical audit" in html
    assert "/signals/consumer/SBER.json" in html
